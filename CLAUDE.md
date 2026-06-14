# A11yWatch

Accessibility auditing & monitoring (SaaS).
- **On-demand:** the extension triggers a scan; the backend *enqueues a job* and a worker runs Playwright + axe-core and stores the issues.
- **Continuous:** a scheduler *enqueues* scans for due sites on a timer; results are diffed against the previous scan and regression alerts are sent.

Scanning is always decoupled: the API and scheduler **enqueue**, workers **scan**. On-demand and scheduled scans run the **same job** — one engine, two triggers.

## Repo map
- `backend/`   — FastAPI API + scan engine + queue/workers + scheduler. See `backend/CLAUDE.md`.
- `extension/` — MV3 Chrome extension (TypeScript + Vite/CRXJS). See `extension/CLAUDE.md`.
- `SPEC.md` — architecture & behavior (source of truth). `PLAN.md` — phased build plan.
- `docs/superpowers/specs/` — longer-form design docs.

## Working here
- Read the relevant subfolder's `CLAUDE.md` before working in `backend/` or `extension/`.
- Follow `PLAN.md` phases; commit at each phase boundary. Specs define behavior — this file is conventions only.

## Don'ts
- Never commit secrets; `.env` is git-ignored — use `.env.example`.
- Never use the word "compliance" in product copy or API responses — say "monitoring", "issues", "regression alerts", "documentation".
- Don't add a dependency or MCP server without a current need.
