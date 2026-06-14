# A11yWatch

Accessibility auditing & monitoring. Run on-demand audits of a page or continuously monitor sites and get alerted on **new** accessibility issues (regressions).

Scanning is decoupled from the API: the FastAPI app and the scheduler only *enqueue* jobs; separate worker processes run headless Chromium (Playwright + axe-core) and write timestamped results to Postgres.

## Stack
- **Backend:** Python 3.12, FastAPI, Postgres, Redis + RQ, APScheduler, Playwright + axe-core (managed with `uv`).
- **Extension:** Manifest V3 Chrome extension (TypeScript + Vite/CRXJS).

## Quick start (after the scaffold)
```bash
docker compose up -d                 # Postgres + Redis
cd backend && uv sync && uv run playwright install chromium
uv run alembic upgrade head          # once migrations exist
uv run fastapi dev src/a11ywatch/main.py
uv run rq worker scans alerts        # in another terminal
uv run python -m a11ywatch.scheduler # in another terminal
```

See `SPEC.md` for architecture and `PLAN.md` for the phased build.
