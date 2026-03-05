#!/usr/bin/env python3
"""Host-only local runner for ai-travel-companion.

Usage:
    python scripts/ai_travel_companion_runner.py start
    python scripts/ai_travel_companion_runner.py stop
    python scripts/ai_travel_companion_runner.py status
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
STATE_DIR = REPO_ROOT / ".run" / "ai-travel-companion"
STATE_FILE = STATE_DIR / "state.json"

BACKEND_PORT = 8000
FRONTEND_PORT = 8080
VOICE_WORKER_PORT = 8082


@dataclass
class ServiceProc:
    name: str
    cmd: list[str]
    cwd: Path
    process: subprocess.Popen[str] | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ai-travel-companion local runner")
    sub = parser.add_subparsers(dest="command", required=False)

    start = sub.add_parser("start", help="start all local services")
    start.add_argument("--detach", action="store_true", help="run in background")
    start.add_argument(
        "--skip-smoke",
        action="store_true",
        help="skip post-start smoke checks",
    )

    sub.add_parser("stop", help="stop all local services")
    sub.add_parser("status", help="show service status")

    parser.set_defaults(command="start")
    return parser.parse_args()


def _load_settings_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def _require_paths() -> None:
    if not (REPO_ROOT / ".env").exists():
        raise RuntimeError("Missing .env file in repository root")
    if not FRONTEND_DIR.exists():
        raise RuntimeError("Missing frontend directory")
    if not (FRONTEND_DIR / "node_modules").exists():
        raise RuntimeError(
            "Missing frontend dependencies. Run: cd frontend && npm ci"
        )


def _read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _write_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _clear_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout_s: float = 60.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def _http_json(url: str, method: str = "GET", data: bytes | None = None) -> tuple[int, Any]:
    req = Request(url=url, method=method, data=data)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=10) as resp:  # nosec: B310 (local URLs only)
        body = resp.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return resp.status, parsed


def _http_status(url: str, method: str = "GET", data: bytes | None = None) -> int:
    req = Request(url=url, method=method, data=data)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=10) as resp:  # nosec: B310 (local URLs only)
        return resp.status


def _pg_isready_check(db_url: str) -> None:
    parsed = urlparse(db_url.replace("+asyncpg", ""))
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    dbname = parsed.path.lstrip("/")
    user = parsed.username or ""
    cmd = ["pg_isready", "-h", host, "-p", port, "-d", dbname, "-U", user]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Postgres not ready: {' '.join(cmd)}\n{proc.stdout.strip()}")


def _redis_check(redis_url: str) -> None:
    parsed = urlparse(redis_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=2):
            return
    except OSError as exc:
        raise RuntimeError(f"Redis not reachable at {host}:{port}: {exc}") from exc


def _neo4j_check(neo4j_url: str) -> None:
    parsed = urlparse(neo4j_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687
    try:
        with socket.create_connection((host, port), timeout=2):
            return
    except OSError as exc:
        raise RuntimeError(f"Neo4j not reachable at {host}:{port}: {exc}") from exc


def _preflight() -> None:
    import shutil

    _load_settings_env()
    _require_paths()

    for bin_name in ("python", "uvicorn", "npm", "node", "pg_isready", "curl"):
        if not shutil.which(bin_name):
            raise RuntimeError(f"Missing required command in PATH: {bin_name}")

    database_url = os.getenv("DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")
    neo4j_uri = os.getenv("NEO4J_URI", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing in .env")
    if not redis_url:
        raise RuntimeError("REDIS_URL is missing in .env")
    if not neo4j_uri:
        raise RuntimeError("NEO4J_URI is missing in .env")

    _pg_isready_check(database_url)
    _redis_check(redis_url)
    _neo4j_check(neo4j_uri)

    ports = {
        BACKEND_PORT: "backend",
        FRONTEND_PORT: "frontend",
        VOICE_WORKER_PORT: "voice-worker",
    }
    occupied = [f"{port}/{label}" for port, label in ports.items() if _is_port_open("127.0.0.1", port)]
    if occupied:
        raise RuntimeError(
            "Required ports are already in use: "
            + ", ".join(occupied)
            + ". Stop existing processes or run `python run_ai_travel_companion.py stop`."
        )


def _spawn_service(spec: ServiceProc, detach: bool) -> ServiceProc:
    if detach:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_file = (STATE_DIR / f"{spec.name}.log").open("a", encoding="utf-8")
        stdout_target: Any = log_file
    else:
        stdout_target = subprocess.PIPE
    spec.process = subprocess.Popen(
        spec.cmd,
        cwd=spec.cwd,
        stdout=stdout_target,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    return spec


def _stream_logs(services: list[ServiceProc], stop_event: threading.Event) -> None:
    out_q: queue.Queue[tuple[str, str]] = queue.Queue()

    def _reader(name: str, stream: Any) -> None:
        try:
            for line in iter(stream.readline, ""):
                out_q.put((name, line.rstrip("\n")))
        finally:
            stream.close()

    threads: list[threading.Thread] = []
    for svc in services:
        assert svc.process is not None
        t = threading.Thread(
            target=_reader,
            args=(svc.name, svc.process.stdout),
            daemon=True,
        )
        t.start()
        threads.append(t)

    while not stop_event.is_set():
        try:
            name, line = out_q.get(timeout=0.2)
            print(f"[{name}] {line}")
        except queue.Empty:
            pass
        if any(svc.process and svc.process.poll() is not None for svc in services):
            stop_event.set()
            break


async def _ws_ping_check() -> None:
    import websockets

    uri = "ws://localhost:8000/api/v1/voice/ws"
    async with websockets.connect(uri, open_timeout=8, close_timeout=5) as ws:
        await ws.recv()  # session_ready
        await ws.send(json.dumps({"type": "ping"}))
        pong = await asyncio.wait_for(ws.recv(), timeout=8)
        if "pong" not in str(pong):
            raise RuntimeError(f"Unexpected websocket response: {pong}")


def _run_smoke_checks() -> None:
    if not _wait_for_port("127.0.0.1", BACKEND_PORT, timeout_s=75):
        raise RuntimeError("Backend did not open port 8000")
    if not _wait_for_port("127.0.0.1", FRONTEND_PORT, timeout_s=90):
        raise RuntimeError("Frontend did not open port 8080")
    if not _wait_for_port("127.0.0.1", VOICE_WORKER_PORT, timeout_s=75):
        raise RuntimeError("Voice worker did not open port 8082")

    status, _ = _http_json("http://localhost:8000/health")
    if status != 200:
        raise RuntimeError(f"/health check failed: {status}")

    status, _ = _http_json("http://localhost:8000/api/v1/voice/health")
    if status != 200:
        raise RuntimeError(f"/api/v1/voice/health check failed: {status}")

    status, payload = _http_json(
        "http://localhost:8000/api/v1/voice/session?language=en&target_language=en",
        method="POST",
        data=b"{}",
    )
    if status != 201:
        raise RuntimeError(f"/api/v1/voice/session check failed: {status}")
    has_livekit_fields = {"room_name", "url", "access_token"}.issubset(set(payload.keys()))
    has_legacy_fields = {"room_name", "room_url", "token"}.issubset(set(payload.keys()))
    if not (has_livekit_fields or has_legacy_fields):
        raise RuntimeError(
            "Voice session payload missing expected keys "
            "(need room_name + (url,access_token) or (room_url,token))"
        )

    status = _http_status("http://localhost:8080/app?mode=solo")
    if status != 200:
        raise RuntimeError(f"Frontend check failed: {status}")

    asyncio.run(_ws_ping_check())


def _start(detach: bool, skip_smoke: bool) -> int:
    existing = _read_state()
    if existing.get("services"):
        alive = [
            svc["name"]
            for svc in existing["services"]
            if _is_pid_alive(int(svc["pid"]))
        ]
        if alive:
            print(f"Already running: {', '.join(alive)}")
            return 1

    _preflight()

    services = [
        ServiceProc(
            name="backend",
            cmd=[
                "uvicorn",
                "src.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(BACKEND_PORT),
            ],
            cwd=REPO_ROOT,
        ),
        ServiceProc(
            name="voice-worker",
            cmd=["python", "src/voice/voice_agent_worker.py"],
            cwd=REPO_ROOT,
        ),
        ServiceProc(
            name="frontend",
            cmd=[
                "npm",
                "run",
                "dev",
                "--",
                "--host",
                "0.0.0.0",
                "--port",
                str(FRONTEND_PORT),
            ],
            cwd=FRONTEND_DIR,
        ),
    ]

    for svc in services:
        _spawn_service(svc, detach=detach)

    _write_state(
        {
            "started_at": int(time.time()),
            "services": [
                {
                    "name": s.name,
                    "pid": s.process.pid,
                    "pgid": os.getpgid(s.process.pid),
                    "cmd": s.cmd,
                }
                for s in services
                if s.process is not None
            ],
        }
    )

    if not skip_smoke:
        _run_smoke_checks()

    print("All services started and verified.")
    print(f"Frontend: http://localhost:{FRONTEND_PORT}/app?mode=solo")
    print(f"Backend:  http://localhost:{BACKEND_PORT}")
    print(f"Worker:   http://localhost:{VOICE_WORKER_PORT}")

    if detach:
        print("Running in detached mode.")
        return 0

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: Any) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    try:
        _stream_logs(services, stop_event)
    finally:
        _stop()
    return 0


def _stop() -> int:
    state = _read_state()
    services = state.get("services", [])
    if not services:
        print("No running state found.")
        return 0

    # Terminate in reverse startup order (frontend -> worker -> backend).
    for svc in reversed(services):
        pid = int(svc["pid"])
        pgid = int(svc.get("pgid", pid))
        if not _is_pid_alive(pid):
            continue
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            continue

    deadline = time.time() + 10
    while time.time() < deadline:
        alive = [int(s["pid"]) for s in services if _is_pid_alive(int(s["pid"]))]
        if not alive:
            break
        time.sleep(0.3)

    for svc in reversed(services):
        pid = int(svc["pid"])
        pgid = int(svc.get("pgid", pid))
        if _is_pid_alive(pid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except OSError:
                pass

    _clear_state()
    print("Stopped ai-travel-companion services.")
    return 0


def _status() -> int:
    state = _read_state()
    services = state.get("services", [])
    if not services:
        print("Status: not running")
        return 0

    if not any(_is_pid_alive(int(svc["pid"])) for svc in services):
        _clear_state()
        print("Status: not running (stale state cleared)")
        return 0

    print("Status:")
    for svc in services:
        pid = int(svc["pid"])
        pgid = int(svc.get("pgid", pid))
        alive = _is_pid_alive(pid)
        print(f"  - {svc['name']}: pid={pid} pgid={pgid} {'up' if alive else 'down'}")

    checks = {
        "frontend:8080": _wait_for_port("127.0.0.1", FRONTEND_PORT, 1),
        "backend:8000": _wait_for_port("127.0.0.1", BACKEND_PORT, 1),
        "worker:8082": _wait_for_port("127.0.0.1", VOICE_WORKER_PORT, 1),
    }
    print("Ports:")
    for name, ok in checks.items():
        print(f"  - {name}: {'open' if ok else 'closed'}")
    return 0


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "start":
            return _start(detach=args.detach, skip_smoke=args.skip_smoke)
        if args.command == "stop":
            return _stop()
        if args.command == "status":
            return _status()
        raise RuntimeError(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
