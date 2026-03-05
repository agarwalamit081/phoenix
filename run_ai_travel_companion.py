#!/usr/bin/env python3
"""Convenience local entrypoint for ai-travel-companion runner.

Examples:
    python run_ai_travel_companion.py
    python run_ai_travel_companion.py start --detach
    python run_ai_travel_companion.py status
    python run_ai_travel_companion.py stop
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ai_travel_companion_runner import main

if __name__ == "__main__":
    raise SystemExit(main())
