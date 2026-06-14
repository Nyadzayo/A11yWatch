# A11yWatch — Build Plan

Phased plan derived from `SPEC.md`. Build top-to-bottom. **Commit at every phase boundary.** Each phase lists entry/exit criteria and tests; phases marked **TDD-first** require writing the named tests and watching them fail *before* implementation.

Robustness requirement IDs (R1–R9) refer to `SPEC.md` §8.

---

## Phase 0 — Scaffold ✅ (this commit)
Repo, `.gitignore`, nested `CLAUDE.md`, `.claude/settings.json` (permissions + ruff hook), `docker-compose.yml` (Postgres + Redis), `pyproject.toml` / `package.json` (deps declared, not installed), `SPEC.md`, `PLAN.md`, directory skeleton.
**Exit:** files committed; no product code yet.

---

## Phase 1 — API skeleton & data layer ✅
**Goal:** a running, tested API with no scanning yet.
**Entry:** Phase 0 committed; `uv sync` + `docker compose up -d` succeed.
**Build:**
- `core/`: settings (pydantic-settings), async DB session, JWT security helpers.
- `models/`: ORM for users/projects/scans/violations/alert_channels/branding (§5); Pydantic schemas; Alembic baseline migration.
- `api/`: auth (register/login/me), project CRUD, error-envelope handler, pagination helper.
- `main.py`: FastAPI app, `/health`, router wiring.
- `POST /projects/{id}/scans` creates a `queued` scan row, enqueues a **no-op** job (returns a `job_id`), and returns 202 with the final `{scan_id, job_id, status:"queued"}` envelope. Phase 3 swaps the no-op for `perform_scan`; the response shape is final now.
**Tests:** auth flow; project CRUD; validation (422) + error envelope shape; pagination.
**Exit:** API tests green; `uv run fastapi dev` serves `/health` and `/api/v1/*`. **Commit.**

---

## Phase 2 — Scan engine & violation diff  · **TDD-first (diff)** ✅
**Goal:** the shared scan engine and the diff logic, runnable in isolation.
**Entry:** Phase 1 committed.
**Build:**
- `scanning/engine.py`: `run_scan(project) -> ScanResult` — page-set resolution (url_list → sitemap → BFS crawl ≤ `max_pages`), navigate, inject axe-core, `axe.run()` per page, collect violations with fingerprints. Chromium lifecycle: one browser per scan, reuse across pages, close in `finally` (**R7**).
- `scanning/diff.py`: fingerprint diff → NEW / RESOLVED vs previous successful scan.
- Persist results (scans + violations rows, counts).
**Tests (write FIRST, confirm red):**
- `test_diff_*`: identical scans → no NEW; added issue → NEW; removed issue → RESOLVED; url/target normalization stability.
- Then: engine tests with a **mocked** Playwright page (stub axe results) — crawl cap respected, browser closed on error (**R7**).
**Exit:** diff + engine tests green; engine usable without HTTP/queue. **Commit.**

---

## Phase 3 — Queue, scheduler & concurrency lock  · **TDD-first (lock)** ✅
**Goal:** wire the one engine to both triggers; prevent overlapping scans.
**Entry:** Phase 2 committed.
**Build:**
- `jobs/`: RQ setup, `scans`/`alerts` queues (**R2**), `perform_scan(project_id, trigger)` calling the Phase-2 engine, Redis lock `scan:lock:{project_id}` + DB `status` flag — **lock-before-check** (`SET NX EX`), released on finish, TTL backstop (**R6**).
- `api/`: `POST /projects/{id}/scans` now enqueues `perform_scan(id,"on_demand")`, idempotent (return in-flight scan; honor `Idempotency-Key`).
- `scheduler/`: APScheduler process — query due projects, enqueue `perform_scan(id,"scheduled")` **staggered** (**R8**), **enqueue-only** (**R1**).
- `workers/`: RQ worker entrypoint; prefetch 1 (one job per process); `WORKER_CONCURRENCY` = worker-process count (default 2) (**R3**).
**Tests (write FIRST, confirm red):**
- `test_lock_*`: enqueue while a scan is in-flight → **no double-enqueue** (use `fakeredis`); lock released on completion/failure.
- Then: on-demand and scheduled both enqueue the **same** `perform_scan` (shared path, §4); scheduler never calls the engine directly (**R1**).
**Exit:** lock tests green; double-enqueue impossible; on-demand == scheduled code path. **Commit.**

---

## Phase 4 — Resilience: retries, timeouts, failure handling  · **TDD-first (retry/timeout)** ✅
**Goal:** scans survive flaky sites and never hang or leak.
**Entry:** Phase 3 committed.
**Build:**
- Per-page timeout (~30s) + overall per-site timeout; kill hung loads gracefully (**R4**).
- RQ `Retry(max=2, interval=[4, 8])` → 3 attempts on *transient* failures only; permanent failures fail immediately (**R5**).
- Final failure → mark scan `failed`, log, enqueue **operator** alert (not customer) (**R5**).
- Bounded concurrency config validated (**R3**).
**Tests (write FIRST, confirm red):**
- Mock a **hung** page → per-page/site timeout fires, browser cleaned up.
- Mock a **failing** scan → retried N times with backoff, then `failed` + operator alert; customer NOT alerted.
**Exit:** resilience tests green. **Commit.**

---

## Phase 5 — Alerts & branding ✅
**Goal:** customers hear about regressions; reports can be white-labeled.
**Entry:** Phase 4 committed.
**Build:**
- `alerts/`: `send_alert` job consumes the diff → notify project alert channels on **NEW** issues only; channel CRUD endpoints; email delivery first (webhook/slack stubs).
- Branding endpoints (`GET/PUT /projects/{id}/branding`); store settings for white-label reports.
- Operator vs customer alert routing finalized.
**Tests:** NEW issues → alert enqueued/sent; no NEW issues → silence; operator vs customer routing; channel CRUD.
**Exit:** alert tests green. **Commit.**

---

## Phase 6 — Operator self-monitoring & observability ✅ (MVP complete)
**Goal:** a dead scheduler/worker is detected before customers notice.
**Entry:** Phase 5 committed.
**Build:**
- Scheduler pings `HEALTHCHECK_PING_URL` every cycle (**R9**); missed pings → external alert.
- Structured logging across API/worker/scheduler; scan metrics (duration, pages, failures).
- Operator alerts on repeated failures / stuck `running` scans.
**Tests:** healthcheck pinged each cycle (mocked HTTP); stuck-scan detection.
**Exit:** monitoring tests green. **Commit. MVP complete.**

---

## Extension — Phase E1 — Backend violations read endpoint · **TDD-first** ✅
**Goal:** the read surface the popup needs to show issues.
**Entry:** backend MVP (Phase 6) committed.
**Build:** `GET /scans/{id}/violations` — paginated, `impact` filter, ownership-checked (scan→project→user, 404 for non-owners); `ViolationOut` schema.
**Tests (write FIRST, confirm red):** owned scan returns issues; non-owner → 404; pagination; `impact` filter; empty scan → empty page.
**Exit:** endpoint tests green; `ruff` clean. **Commit.**

## Extension — Phase E2 — Extension core (lib + service worker) · **TDD-first (lib)** ✅
**Goal:** the testable network/session core, no UI yet.
**Entry:** E1 committed.
**Build:** `npm install`; Vitest; `src/lib/` (typed API client w/ Bearer + error-envelope handling, `chrome.storage` session helpers, message types, issue grouping/formatting); `src/background/` service worker message handlers (login, me, audit-current-tab, get-scan, get-violations) — all network here.
**Tests (write FIRST, confirm red):** API client attaches Bearer + parses error envelope + 401 handling; session save/load/clear; issue grouping by impact; audit-current-tab find-or-create logic.
**Exit:** Vitest green; `tsc --noEmit` clean. **Commit.**

## Extension — Phase E3 — Popup UI ✅ (extension MVP complete)
**Goal:** the working popup end-to-end against the running API.
**Entry:** E2 committed.
**Build:** Login view (email/password + register toggle + API URL) and Audit view (trigger + poll + grouped issue list + counts); wire to the worker; `manifest.json` (popup, `host_permissions`).
**Verify:** `npm run build`; load unpacked; audit a page against the running backend (manual, no UI test runner).
**Exit:** popup audits a page and renders issues. **Commit. Extension MVP complete.**

## Dashboard — Phase D1 — Server-rendered web dashboard · **TDD-first**
**Goal:** view + manage + trigger scans from a browser, served by the API (no extension, no build step).
**Entry:** backend MVP committed.
**Build:** `web/` module — cookie auth (login/logout/register, httpOnly SameSite=Lax JWT cookie, reuse `core/security`), Jinja2 templates, routes: `/login`, `/` (projects + new-project form), `/projects/{id}` (scans + "Scan now"), `/scans/{id}` (issues grouped by impact, auto-refresh). "Scan now" reuses `enqueue_scan`. Mounted on the app root.
**Tests (write FIRST, confirm red):** logged-out protected page → 303 `/login`; login sets cookie → `/` 200; dashboard lists only the owner's projects; scan page renders issues grouped by impact; "Scan now" enqueues (fakeredis); no "compliance" in rendered HTML.
**Exit:** dashboard tests green; `ruff` clean. **Commit.**

## Dashboard completion — Phases D2–D6
Audit (2026-06-14) against the MVP must-haves found: Scan-now ✅; Auth+add-project ⚠️ (form lacks frequency/sitemap/page-list though the model has the columns); per-site detail ⚠️ (no issue-count-over-time / trend); multi-site overview ❌ (no counts/severity/trend); white-label PDF ❌ (Branding API exists, no UI/report); alert settings ❌ (AlertChannel API exists, no UI). Each phase is **TDD-first**, committed on its own, with a review pause between phases. Out of scope (confirmed absent, keep out): team seats/roles, CMS/CI integrations, VPAT, in-app billing.

### Phase D2 — Per-site detail: history + trend · **TDD-first (trend)** ✅
Pure `web/trends.py::scan_trend(current, previous)` → improved/regressed/unchanged/no_baseline + signed change (fewer issues = better). Project page gains an issue-count-over-time view (CSS bars, no chart lib) and a trend badge vs. the previous succeeded scan.
**Tests:** `test_trends.py` (improved/regressed/unchanged/no_baseline); project page renders trend badge + history bars.

### Phase D3 — Multi-site overview
Reuse `scan_trend`. `/` table gains per-project current issue count, severity breakdown, last-scanned, and a better/worse trend badge, via aggregate queries (no N+1).
**Tests:** per-project rollup (counts + severity); trend badge reflects latest-vs-previous.

### Phase D4 — Add-project completeness
Extend the add-project form + `create_project_web` to capture scan frequency (daily/weekly/hourly → minutes), optional sitemap URL, optional page list (→ `url_list`), optional `max_pages`, with validation.
**Tests:** form persists the new fields; invalid frequency/URL rejected.

### Phase D5 — White-label report
Branding settings form + a print-optimized report page (agency logo + name, latest scan summary, "N new / M fixed" diff, timestamp). PDF via browser print (no new dependency).
**Tests:** report renders branding + diff summary; only the owner can view.

### Phase D6 — Alert settings
Dashboard form to list/add/remove email + optional Slack webhook channels, wired to the existing `AlertChannel` logic.
**Tests:** add email channel persists; add Slack webhook persists; delete removes; non-owner blocked.

## Cross-cutting
- **Definition of done (per phase):** named tests green, `ruff check`/`format` clean, committed.
- **No silent scope cuts:** if a phase drops a requirement, note it here.
- **Copy guard:** a pre-commit/CI step greps source + copy for "compliance" (case-insensitive) and fails on any match — turning the no-"compliance" rule into a guarantee, not a convention.
- **Traceability:** R1 P1/P3 · R2 P3 · R3 P3/P4 · R4 P4 · R5 P4 · R6 P3 · R7 P2 · R8 P3 · R9 P6. On-demand==scheduled (§4) verified P3. No "compliance" copy: enforced repo-wide.
