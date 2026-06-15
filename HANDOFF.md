# A11yWatch — Handover (2026-06-15)

Pick up here in a fresh context window. Read this, then `SPEC.md §15` and `PLAN.md` (stages S1–S7).

## TL;DR — where we are
- **Backend MVP (Phases 0–6) ✅**, **Chrome extension MVP (E1–E3) ✅**, **server-rendered dashboard (D1–D6 + adversarial review fixes) ✅** — all committed; **213 non-integration tests green**, ruff clean.
- Just finished: a full audit of the codebase against a new **"production-grade MVP v2"** spec (the false-positive/noise engine, triage, entitlements/monetization, white-label PDF, AI fixes). The plan is recorded in **`SPEC.md` §15** and **`PLAN.md` (stages S1–S7)**. **Implementation has NOT started.**
- **Next action:** implement **Stage S1** (Issue/Occurrence model + fingerprint v2 + dedup + axe `incomplete` classification), **TDD-first**, then PAUSE for review at the S1 gate.

## Hard constraints (do not violate)
- **Never** the word **"compliance"/"compliant"** anywhere — code, API, copy. Use *issues / monitoring / regression alerts / documentation*. (A copy-guard test enforces this.)
- **No `Co-Authored-By` trailers** on commits (user preference).
- **Do NOT touch the user's other app on `:8000`** (a separate Django/PrimeCircle project). Run A11yWatch on **`:8088`**.
- **Assistant cannot enter passwords or create accounts** (even throwaway/localhost) or submit forms without explicit per-action OK — hand those to the user. For local dashboard viewing, the user logs in themselves (the Chrome extension sandboxes cookies, so JS cookie-injection does not work).
- **Don't add dependencies without a current need.** Stripe (S4) and Anthropic/Claude SDK (S7) are pre-approved by the plan but confirm at the stage.

## How to run / test
```bash
docker compose up -d                         # Postgres :55432, Redis :6379
uv sync --directory backend
uv run --directory backend pytest            # 213 non-integration green
uv run --directory backend ruff check src tests && uv run --directory backend ruff format --check src tests
# API (NOTE: :8000 is the user's other app — use :8088):
uv run --directory backend uvicorn a11ywatch.main:app --host 127.0.0.1 --port 8088
# Worker / scheduler:
uv run --directory backend rq worker scans alerts
uv run --directory backend python -m a11ywatch.scheduler
# Dashboard: open http://localhost:8088 (cookie login). Extension: cd extension && npm test && npm run build (load unpacked).
```
Test DB `a11ywatch_test` is auto-created/reset by `tests/conftest.py`. Dashboard reads the dev DB from `backend/.env`.

## What already exists (committed)
- **Backend:** FastAPI + SQLAlchemy 2 async + asyncpg + Alembic; RQ (`scans`/`alerts` queues) + APScheduler; Playwright + axe-core; bcrypt + JWT; pydantic v2; `/api/v1`; structured JSON logs + scan metrics; reaper + healthcheck. **One scan engine** reached via `jobs/dispatch.py::enqueue_scan` from extension, scheduler, AND dashboard (per-project Redis lock + DB gate = idempotent, no double-enqueue).
- **Models (`models/tables.py`):** users, projects, scans, **violations** (per-scan only), alert_channels, branding.
- **Scan pipeline:** `scanning/{engine,playwright_scanner,crawl,fingerprint,diff,persist,types}.py`. Fingerprint today = `sha256(rule_id | normalized_url | target)` — see "highest-risk" below.
- **Dashboard (`web/`):** overview with issue counts/severity/trend (D3), project detail with issues-over-time + trend (D2), add-project settings (D4: frequency/sitemap/url_list/max_pages), white-label **print** report + branding (D5), regression-alert settings (D6). Pure helpers `web/trends.py` (`scan_trend`), `web/forms.py` (project/branding/alert parsers). Cookie auth, CSRF Origin check, constant-work login.
- **Extension (`extension/`):** MV3 popup (login + audit page), service worker owns all network, Vitest-covered `src/lib`.

## The approved v2 plan (SPEC §15, PLAN S1–S7)
Build order, PAUSE for review at each gate, TDD-first:
- **S1** — Issue + Occurrence model · fingerprint v2 · dedup · axe `incomplete` classification. *(write-first tests: DOM-mutation fingerprint stability, dedup one-component-on-N-pages, needs-review never in headline/alerts)* — **foundation; nothing else is correct without it.**
- **S2** — Triage + scoped/persistent/attributed dismissal + immutable status log. *(write-first: dismissal persists across scans)*
- **S3** — Dismissal-aware **issue-level** regression diff → existing alert queue + queue-depth observability. *(write-first: new alerts / dismissed silent / fixed→reappear = regression)*
- **S4** — Accounts + entitlements + usage metering + **server-side** gating + Stripe. *(write-first: paid endpoint rejects free/over-cap)*
- **S5** — Server-side white-label **PDF** (`page.pdf()`) from deduped issues, dismissals respected.
- **S6** — Dashboard reads deduped Issues + documentation/remediation history export.
- **S7** — AI explanations (metered, cached by `(rule_id, fingerprint)`) + accessibility statement generator.

### Approved decisions (defaults the user accepted)
1. **Fingerprint v2 source:** no-scanner-injection version first — node attributes + accessible-name parsed from axe's `html` snippet + a normalized selector *shape* (strip `nth-child`/dynamic tokens) + failure-reason. Add fuller ancestry (needs injecting JS into the axe run) only if dedup proves too coarse.
2. **`violations` table:** repurpose into **`occurrences`** (FK to new `issues`); greenfield migration (dev data only — drop & recreate).
3. **Accounts:** add `accounts` with **1 user→1 account** for MVP; hang plan/entitlement/usage/branding off the account; add `account_id` to projects; defer true multi-seat.
4. **New deps:** Stripe SDK (S4), Anthropic/Claude SDK (S7) — pre-approved, confirm at the stage.

## Highest-risk area — fingerprint v2 (SPEC §15.2)
Current fingerprint **bakes `page_url` in** (→ cross-page dedup impossible by design) and uses the **raw axe CSS `target`** (brittle: nth-child/hashed classes change it → fake "new issue" regressions and broken dismissal persistence). S1 must make it **page-independent** (`page_url` moves to Occurrence) with a **stable element signature** + a **configurable dynamic class/id regex filter** in settings. **Write the DOM-mutation stability tests FIRST** (reordered siblings, inserted wrapper div, changed dynamic/hashed class → SAME fingerprint; distinct issues → DIFFERENT).

## How to execute S1 (recommended, per ultracode)
1. **Understand pass (Workflow):** parallel readers over `scanning/*`, `models/tables.py`, `scanning/persist.py`, `api/scans.py`, `web/router.py` → confirm exact touch-points and current fingerprint/diff/persist flow.
2. **TDD-first:** write the §7 write-first tests and watch them RED before implementing.
3. **Implement:** scanner captures all four axe buckets (`violations`/`incomplete`/`passes`/`inapplicable`); fingerprint v2 + configurable filter in `core/config.py`; new `issues`/`occurrences`/`needs_review` tables + Alembic migration; `persist` upserts Issues + appends Occurrences (first/last seen) + stores needs_review + passes/inapplicable counts; headline = distinct Issues + `pages_affected`.
4. **Adversarial review (Workflow):** correctness + injection pass before commit (the dashboard work caught real bugs this way).
5. **Commit at the S1 gate; PAUSE for the user's review** before S2.

Files likely touched in S1: `scanning/fingerprint.py`, `scanning/playwright_scanner.py`, `scanning/types.py`, `scanning/persist.py`, `scanning/diff.py`, `models/tables.py`, `models/schemas.py`, `core/config.py`, `web/router.py`, `api/scans.py`, new Alembic migration, `tests/`.

## Git
- Branch `main`. **No remote configured** — add one (`git remote add origin <url>`) before `git push`.
- Recent commits (newest first): `c0909cb` PLAN done · `dc1b28e` D6 · `647f70d` review fixes · `2da0827` D5 · `bcaff08` D4 · `305cf2d` D3 · `504a5b7` D2.
- This checkpoint commits: `SPEC.md`, `PLAN.md`, `HANDOFF.md`. `.claude/` is local session state — left untracked (consider adding to `.gitignore`).

## Running background processes from this session (may have been killed)
- `uvicorn` API on **:8088** (fresh current code). Restart with the run command above if down.
- An old stale `:8088` server was killed (it had served new templates with old Python → "No projects yet" bug; restarting from current code fixed it).
