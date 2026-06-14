# A11yWatch — Architecture & Behavior Spec

Status: **design / pre-implementation**. This is the source of truth for behavior. Build order lives in `PLAN.md`.

## 1. Product

A11yWatch runs **accessibility audits** of web pages and **monitors** sites over time.

- **On-demand audit** — a user (via the Chrome extension or API) triggers an audit of a page/site. The backend enqueues a scan job; a worker runs it and stores timestamped results the user can read back.
- **Continuous monitoring** — a user registers a *project* (a site + a scan frequency). A scheduler enqueues scans on a timer. Each scan is diffed against the previous one; **new** issues (regressions) trigger alerts.

Both modes are the **same scan**, triggered two ways (see §4).

### Copy & terminology (non-negotiable)
Never use the word **"compliance"** anywhere in code, API responses, reports, or UI copy. Use **"monitoring", "issues", "regression alerts", "documentation"**. We report what automated checks find; we do not certify legal compliance.

## 2. Architecture overview

```
   ┌─────────────┐                 ┌──────────────────────┐
   │  Extension  │                 │   Scheduler          │  APScheduler, own process
   │  (MV3)      │                 │   ENQUEUE ONLY        │  - find due projects
   └──────┬──────┘                 └──────────┬───────────┘  - stagger enqueues
          │ POST /api/v1/.../scans            │              - ping healthcheck each cycle
          ▼                                   │ enqueue perform_scan(project_id)
   ┌──────────────────────────────────────┐  │
   │   FastAPI API (/api/v1, async)        │  │   ENQUEUE ONLY — never scans
   └──────────────────┬───────────────────┘  │
                      │ enqueue perform_scan(project_id)
                      ▼                       ▼
              ┌───────────────────────────────────┐
              │      Redis  +  RQ                  │
              │   queue "scans"   queue "alerts"   │   separate queues
              └───────┬───────────────────┬───────┘
            one job at a time              │
                      ▼                    ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │  Scan worker(s)      │   │  Alert worker(s)      │
        │  Playwright + axe    │   │  email / operator     │
        │  = the shared engine │   └──────────────────────┘
        └─────────┬────────────┘
                  │ write timestamped results; diff vs previous scan;
                  │ enqueue alert job for NEW issues
                  ▼
        ┌──────────────────────┐
        │      Postgres        │
        └──────────────────────┘
```

**Processes:** API (uvicorn), scan worker(s), alert worker(s), scheduler — all independent. Scaling = run more workers, not code changes. Infra: Postgres + Redis (`docker compose`).

## 3. Components

- **API (`api/`, `core/`)** — FastAPI, `/api/v1`, async, JWT auth. Owns CRUD and *enqueuing*. Returns immediately; never blocks on a scan.
- **Queue (`jobs/`)** — thin wrapper over RQ. Defines `perform_scan(project_id, trigger)` and `send_alert(...)`, the two queues, the concurrency lock, and retry policy. All queue access goes through here so the backend (RQ today) is swappable.
- **Scan engine (`scanning/`)** — the single code path that audits a site. Pure-ish, sync (runs inside a worker). Given a project, it crawls pages, injects axe-core, collects issues, and returns a structured result. Knows nothing about HTTP or scheduling.
- **Workers (`workers/`)** — RQ worker entrypoint(s). Pull one job at a time; call the engine; persist results; trigger the diff→alert step.
- **Scheduler (`scheduler/`)** — APScheduler in its own process. Each cycle: query projects due for a scan, enqueue them (staggered), and ping the operator healthcheck. **Never scans.**
- **Alerts (`alerts/`)** — computes the violation diff and delivers alerts. Customer alerts for NEW issues; operator alerts for scan failures.
- **Data (`models/`)** — SQLAlchemy 2.0 async ORM + Pydantic v2 schemas, Alembic migrations.

## 4. Core principle: one engine, two triggers

`perform_scan(project_id, trigger)` is the **only** way a scan runs.
- **On-demand:** `POST /projects/{id}/scans` enqueues `perform_scan(id, "on_demand")` and returns a scan/job id (202). Non-blocking.
- **Scheduled:** the scheduler enqueues `perform_scan(id, "scheduled")` for each due project.

There is no second scanner. `trigger` is metadata only; the work is identical. This is a hard constraint — do not build a separate scheduled-scan path.

## 5. Data model (Postgres)

- **users** — `id, email (unique), password_hash, created_at`.
- **projects** — `id, user_id, name, base_url, scan_frequency_minutes, sitemap_url?, url_list (json[]?), max_pages?, status (idle|queued|running|failed), last_scan_at?, last_scan_id?, created_at, updated_at`.
- **scans** — `id, project_id, status (queued|running|succeeded|failed), trigger (on_demand|scheduled), job_id?, started_at?, finished_at?, pages_scanned, total_issues, new_issues, resolved_issues, error?, created_at`.
- **violations** — `id, scan_id, project_id, page_url, rule_id, impact (minor|moderate|serious|critical), help, help_url, target (selector), html_snippet, fingerprint, created_at`.
  - `fingerprint = sha256(rule_id + "|" + normalized_page_url + "|" + target)` — the diff key.
  - `normalized_page_url` = absolute URL, lowercase scheme+host, fragment removed, trailing slash stripped, query params sorted by key, tracking params (`utm_*`, `gclid`, `fbclid`) dropped — stable across runs (covered by the Phase-2 diff tests).
- **alert_channels** — `id, project_id, type (email|webhook|slack), target, events (json: ["new_issues"]), enabled`.
- **branding** — `id, project_id (unique), company_name?, logo_url?, primary_color?, report_footer?` (white-label report settings; stored now, rendered later).

Operator alerting (scan failures) is configured globally via `OPERATOR_ALERT_EMAIL`, not per project.

**Status state machines.** `scan.status`: `queued → running → succeeded | failed`. `project.status` reflects the *latest/in-flight* scan: `idle → queued` (on enqueue) `→ running` (on worker start) `→ idle | failed` (on finish) — no `succeeded` because a project rests at `idle` between scans. Idempotency (§6) keys off `project.status ∈ {queued, running}`.

## 6. API design (`/api/v1`, async, Pydantic v2)

**Auth (JWT):** `POST /auth/register`, `POST /auth/login` → access token, `GET /auth/me`.

**Projects:** `POST /projects` · `GET /projects` (paginated) · `GET /projects/{id}` · `PATCH /projects/{id}` · `DELETE /projects/{id}`.

**Scans:**
- `POST /projects/{id}/scans` — trigger on-demand scan. **Enqueues, returns `{scan_id, job_id, status:"queued"}` (202). Never blocks.** Idempotent (see below).
- `GET /projects/{id}/scans` — history (paginated).
- `GET /scans/{id}` — status + summary (`pages_scanned`, `total/new/resolved` counts).
- `GET /scans/{id}/violations` — issues (paginated, filter by impact/page).
- `GET /scans/{id}/diff` — NEW vs RESOLVED vs previous successful scan.
- `GET /projects/{id}/latest` — latest scan results + diff.

**Alert channels:** `GET/POST/PATCH/DELETE /projects/{id}/alert-channels`.
**Branding:** `GET/PUT /projects/{id}/branding`.
**Health:** `GET /health` (liveness).

**Conventions**
- **Error envelope:** `{"error": {"code": "...", "message": "...", "details": [...]}}` on every 4xx/5xx.
- **Validation:** Pydantic v2 request models; 422 on bad input.
- **Pagination:** `?limit=&offset=`; response `{"items":[...], "total":N, "limit":L, "offset":O}`.
- **Idempotency on scan trigger (no double-enqueue):** `POST /projects/{id}/scans` is **lock-before-check**: (1) DB gate — if a *non-stale* queued/running scan exists for the project, return it (200); (2) else acquire Redis lock `scan:lock:{project_id}` via `SET NX EX`; if not acquired, return the in-flight scan; (3) else create a `queued` scan and enqueue the shared job (with `job_timeout = site_timeout`), return 202. Active scans older than the lock window are treated as abandoned, so a crashed worker can't wedge the project (the DB gate and the Redis TTL agree). The worker releases the lock on success **and** failure; `TTL = site_timeout + stagger delay + buffer` is the backstop. An optional `Idempotency-Key` header dedupes retried POSTs.

## 7. Scan engine

1. **Page set:** use `url_list` if provided, else fetch `sitemap_url`, else BFS-crawl same-origin internal links from `base_url` up to `max_pages` (default `SCAN_MAX_PAGES`).
2. **Per page:** navigate (timeout `SCAN_PAGE_TIMEOUT_SECONDS`, default 30s), inject axe-core, run `axe.run()`, collect violations.
3. **Persist:** write a `scans` row and `violations` rows with timestamps and fingerprints.
4. **Diff:** compare fingerprints to the previous **successful** scan → NEW / RESOLVED sets; store counts on the scan; if NEW issues exist, enqueue `send_alert` on the `alerts` queue.

**Timeouts & failure classification.** Two limits apply: the per-page timeout (step 2) and an overall per-site timeout `SCAN_SITE_TIMEOUT_SECONDS` (default 600s) guarding the whole scan; if either fires, the page/scan is killed gracefully and the scan is marked `failed`. *Transient* failures (page/site timeout, connection reset, TLS error, browser crash, transient DB/Redis error) are retryable (§8 R5); *permanent* failures (malformed URL, persistent 4xx) fail immediately without retry.

**Chromium lifecycle (non-negotiable):** launch one headless browser per scan; reuse it across pages where safe; always close pages/contexts/browser in `finally`, including on error — no leaked processes/RAM.

## 8. Robustness requirements (non-negotiable)

| # | Requirement |
|---|---|
| R1 | Scheduler **only enqueues**; it never runs a scan. |
| R2 | Separate `scans` and `alerts` queues so a flaky email provider can't block scanning. |
| R3 | Each worker **process** pulls **one job at a time** (RQ prefetch 1). `WORKER_CONCURRENCY` = number of worker processes (default **2**, range 2–4) = max parallel scans. Scale by adding processes, not code. |
| R4 | **Per-page timeout** (~30s) **and overall per-site timeout** (`SCAN_SITE_TIMEOUT_SECONDS`); hung page loads are killed gracefully. |
| R5 | **Retries with backoff** on *transient* failures: 3 total attempts (1 + 2 retries) via RQ `Retry(max=2, interval=[4, 8])` (increasing delays). After final failure: mark scan `failed`, log it, and alert the **operator** (not the customer). |
| R6 | **Concurrency lock / idempotency** — a project mid-scan is never enqueued again (DB `status` flag + Redis lock `scan:lock:{project_id}`). No overlapping scans of the same site. |
| R7 | **Graceful Chromium lifecycle** — always close pages/contexts/browser on error; reuse one browser per scan. |
| R8 | **Stagger** scheduled enqueues (`SCHEDULER_STAGGER_SECONDS`) instead of firing all scans at once; target off-peak windows. |
| R9 | **Operator self-monitoring** — ping `HEALTHCHECK_PING_URL` (e.g. Healthchecks.io) every scheduler cycle so a dead scheduler is detected before customers notice. |

## 9. Key decisions & rationale

- **RQ over Celery (queue).** Redis-native, minimal ops, pairs cleanly with APScheduler-as-enqueuer, and supports separate queues plus `Retry(max, interval=[...])` for increasing-delay retries. To retry *only* transient errors, the job re-raises on transient exceptions and marks permanent failures `failed` without re-raising. All access is behind `jobs/`, so Celery is a localized swap if we outgrow RQ.
- **APScheduler as enqueuer (not Celery beat).** Keeps scheduling explicit, queue-agnostic, and easy to add staggering + the healthcheck ping.
- **SQLAlchemy 2.0 async + asyncpg + Alembic.** Mature async ORM with migrations; Pydantic schemas kept separate from ORM models.
- **Sync Playwright inside workers; async API.** RQ jobs run sync, so the engine uses Playwright's sync API — no event-loop-in-worker complexity. Handlers stay async and only enqueue. Clean sync/async boundary.
- **Diff by fingerprint** of `rule_id + normalized url + target` — stable across runs, drives NEW/RESOLVED detection.

## 10. Testing strategy

- **TDD, tests first (write failing, confirm red, then implement):**
  - **Violation diff** logic — NEW/RESOLVED across two scans (Phase 2).
  - **Concurrency lock / no-double-enqueue** (Phase 3).
- **Also covered:** retry + timeout behavior with a **mocked hung/failing** scan (Phase 4); core API endpoints (Phase 1+).
- **Tooling:** pytest + pytest-asyncio; `fakeredis` for lock/queue tests; `httpx.AsyncClient` for the API; `pytest-mock`/monkeypatch to stub Playwright in unit tests (no real browser in unit tests).

## 11. Out of scope (MVP)
Billing/payments; teams/roles beyond a single owner; PDF rendering of white-label reports (branding is stored, not rendered); a client-side dashboard SPA (a **minimal server-rendered dashboard** ships — see §14; the extension remains the quick-audit viewer); SSO/OAuth; quotas/rate-limiting; i18n.

## 12. Open questions (defaults chosen; confirm during build)
- `scan_frequency_minutes` (interval) vs cron expressions — **default: interval minutes**.
- Alert channel types for MVP — **default: email first**, webhook/slack stubs.
- How the extension authenticates — **default: user JWT**; per-project API keys later.

## 13. Extension (MVP)

Manifest V3, TypeScript + Vite/CRXJS. From the toolbar **popup**, audit the current tab server-side and show its issues.

- **Service worker (`src/background/`)** owns *all* backend calls (login, `/auth/me`, audit-current-tab, get-scan, get-violations). No in-memory state — reads `{token, baseUrl}` from `chrome.storage.local` per call; listeners registered at top level; `host_permissions` for the API origin so cross-origin fetches need no CORS handling.
- **Popup (`src/popup/`)** is the only UI — plain TS + minimal DOM, two views (**Login**, **Audit**). Talks to the worker via typed `chrome.runtime.sendMessage`. **No content script** (the backend scans the URL via Playwright; `activeTab` supplies the tab URL). Permissions: `activeTab`, `storage`, host.
- **Shared lib (`src/lib/`)** — Vitest-covered core: typed API client (Bearer auth, error-envelope handling), session storage helpers, message types, issue grouping/formatting.
- **Auth:** one-time email/password login (with a register toggle); JWT + base URL stored in `chrome.storage.local`; auto-resume when the session is valid (`/auth/me`), logout control. Default base URL `http://localhost:8000`.
- **Audit flow:** active-tab URL → find-or-create a project for that exact URL (`url_list:[url]`, `max_pages:1`) → `POST /projects/{id}/scans` → poll `GET /scans/{id}` until `succeeded`/`failed` → `GET /scans/{id}/violations` → render grouped by impact (critical→minor) with rule, help link, selector, and total/new/resolved counts. The in-flight `scan_id` is persisted so closing/reopening the popup resumes polling.
- **Read surface used:** `GET /scans/{id}/violations` (paginated, `impact` filter, ownership-checked). `GET /projects/{id}/latest` and `GET /scans/{id}/diff` remain deferred (counts ride on `ScanOut`).
- **Copy:** never "compliance" — "issues", "monitoring", "regression alerts".

## 14. Web dashboard (server-rendered)

A minimal browser dashboard served by the API itself (`web/`, Jinja2), mounted on the same app at the root — no build step, no extension required. Open the API origin in a browser.

- **Auth:** browser cookie, reusing `core/security`. `POST /login` validates with `verify_password`, mints the same JWT via `create_access_token`, stores it in an **httpOnly, SameSite=Lax** cookie (`secure` in production); a cookie-auth dependency redirects to `/login` (303) when absent/invalid. `POST /logout` clears it. Register supported from the login page.
- **Pages:** `/login`; `/` (your projects + a "new project" form); `/projects/{id}` (scan history + "Scan now"); `/scans/{id}` (status + issues grouped by impact, auto-refresh while `queued`/`running`).
- **Reuse:** "Scan now" calls the same `enqueue_scan` (one engine — now reachable from extension, scheduler, **and** dashboard); reads hit the existing tables. Dashboard-created projects monitor the whole site (default crawl) vs the extension's single-page audit.
- **Safety:** Jinja2 autoescaping (XSS); SameSite=Lax mitigates CSRF on state-changing POSTs for the MVP (full CSRF tokens are a follow-up); ownership-checked on every page. **Copy:** never "compliance".
