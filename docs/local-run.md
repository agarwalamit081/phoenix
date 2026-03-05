# Local One-Command Run

This repo supports a single host-only Python command (no Docker/Kubernetes):

- `python run_ai_travel_companion.py` (same as `start`)
- `python run_ai_travel_companion.py stop`
- `python run_ai_travel_companion.py status`

## Preconditions

The runner fails fast if any required host dependency is unavailable:

- PostgreSQL (`DATABASE_URL` from `.env`) via `pg_isready`
- Redis (`REDIS_URL` from `.env`)
- Neo4j (`NEO4J_URI` from `.env`)
- Frontend dependencies (`frontend/node_modules`)
- CLI tools: `python`, `uvicorn`, `npm`, `node`, `pg_isready`, `curl`

No automatic package installation is performed.

## Start

```bash
python run_ai_travel_companion.py
```

This launches and verifies:

- Frontend: `http://localhost:8080/app?mode=solo`
- Backend: `http://localhost:8000`
- Voice worker mgmt: `http://localhost:8082`

Smoke checks include:

- `GET /health`
- `GET /api/v1/voice/health`
- `POST /api/v1/voice/session`
- Voice WebSocket ping/pong
- Frontend URL reachability

## Stop / Status

```bash
python run_ai_travel_companion.py status
python run_ai_travel_companion.py stop
```

The runner stores process state in `.run/ai-travel-companion/state.json`.
