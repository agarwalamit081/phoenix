# Repository Guidelines

## Project Structure & Module Organization
Backend code lives in `src/`, organized by domain: `api/v1` (FastAPI routes), `services/` (business logic), `workflows/`, `database/`, and supporting packages like `routing/`, `rag/`, and `voice/`. Tests are in `tests/` with `unit/`, `integration/`, `e2e/`, and `performance/` suites. Frontend code is in `frontend/src/` (Vite + React + TypeScript). `sample-ui/` contains exploratory UI work; treat it as non-primary unless a task explicitly targets it. Infrastructure and local dependencies are defined in `docker-compose.yml`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`: create Python env and install backend deps.
- `uvicorn src.main:app --reload`: run backend locally (API/health/docs in debug mode).
- `pytest`: run all backend tests with coverage (`--cov-fail-under=87` enforced).
- `pytest -m "unit"` or `pytest tests/integration`: run focused test suites.
- `cd frontend && npm install`: install frontend deps.
- `cd frontend && npm run dev`: run frontend locally.
- `cd frontend && npm run build`, `npm run lint`, `npm run test`: build, lint, and run Vitest.
- `docker compose up -d`: start PostgreSQL, Redis, and Neo4j for local integration.
- `python run_ai_travel_companion.py`: one-command host-only startup (frontend/backend/voice worker + smoke checks). See `docs/local-run.md`.

## Coding Style & Naming Conventions
Python uses Black (line length 100), Ruff, isort, and mypy (Python 3.12, strict typing). Use `snake_case` for functions/modules, `PascalCase` for classes, and clear domain-oriented filenames (for example, `preference_service.py`). TypeScript/React follows ESLint + TypeScript rules; component files use `PascalCase.tsx`, hooks use `useX.ts`. Prefer small, focused modules and keep API schemas in `src/schemas/`.

## Testing Guidelines
Backend tests use `pytest`, `pytest-asyncio`, and coverage reporting to terminal + `htmlcov/`. Name tests `test_*.py` and test functions `test_*`. Use markers (`unit`, `integration`, `e2e`, `performance`, `slow`) to scope runs. Frontend tests use Vitest and Testing Library (`frontend/src/test/`).

## Commit & Pull Request Guidelines
Follow Conventional Commits as seen in history: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`, `docs: ...`, `test(scope): ...`. Keep commits focused and include impacted area scope (for example, `fix(api)` or `feat(workflow)`). PRs should include: concise summary, linked issue/task, test evidence (commands + results), and screenshots for UI changes.

## Security & Configuration Tips
Use `.env` for local secrets; do not commit credentials. Prefer `.env.example` as the template for required variables. Validate service connectivity via `/health` before running integration workflows.
