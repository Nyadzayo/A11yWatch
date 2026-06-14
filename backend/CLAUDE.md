# Backend — A11yWatch (Python 3.12, uv, FastAPI)

Accessibility scan engine + monitoring API + queue/workers + scheduler.

## Architecture (do not violate)
- API handlers and the scheduler **never scan** — they only **enqueue** jobs (Redis/RQ).
- On-demand and scheduled scans enqueue the **same** job (`jobs/scan.py`) — one engine, two triggers.
- The scan engine (`scanning/`) runs in **worker** processes (sync Playwright). Handlers stay async and non-blocking.

## Commands
- `docker compose up -d`                       # Postgres + Redis (run from repo root)
- `uv run fastapi dev src/a11ywatch/main.py`   # API
- `uv run python -m a11ywatch.workers`         # worker (scans + alerts queues, with scheduler)
- `uv run python -m a11ywatch.scheduler`       # scheduler (enqueues due scans)
- `uv run pytest`                              # tests (`uv run pytest path::test -v` for one)
- `uv run ruff check . && uv run ruff format .`
- `uv run alembic upgrade head`                # migrations
- `uv run playwright install chromium`         # one-time browser download

## Layout
- `api/` routers (`/api/v1`) · `core/` config+db+security · `models/` ORM + Pydantic schemas
- `scanning/` the shared scan engine · `jobs/` RQ setup + job fns + locks · `scheduler/` APScheduler
- `alerts/` diff→alert + delivery · `workers/` worker entrypoint

## Conventions
- uv only (never pip). Pydantic v2. `async def` endpoints. Inject deps via `Depends()`.
- Type hints everywhere. Config via pydantic-settings (env vars, not literals).
- DB access via SQLAlchemy 2.0 async in repositories/helpers — no raw SQL in handlers.
- Scan engine: always close Playwright pages/contexts in `finally`; reuse one browser per scan.

## Avoid
- No scanning in request handlers or the scheduler. No sync/blocking I/O in async handlers.
- No `print()` — use logging.
- Never use "compliance" in code/responses/copy — use "monitoring", "issues", "regression alerts", "documentation".
