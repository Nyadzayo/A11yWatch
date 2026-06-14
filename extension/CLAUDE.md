# Extension — A11yWatch (Manifest V3, TypeScript + Vite/CRXJS)

Trigger on-demand accessibility audits of the current tab and show issues; light viewer for the monitoring dashboard. (Background worker + popup land in Phase 1.)

## Commands
- `npm install` · `npm run dev` (watch) · `npm run build` (bundle → `dist/`)
- Reload the unpacked extension at `chrome://extensions` after building (no automated UI test runner).

## MV3 gotchas (commonly gotten wrong)
- Service worker is **not** persistent — never hold state in memory; use `chrome.storage`.
- Register all event listeners at the **top level** of the service worker.
- Content scripts run in an isolated world — talk to the worker via `chrome.runtime.sendMessage`.
- Request minimal permissions (`activeTab` + specific host permissions) — never `<all_urls>`.

## Backend contract & copy
- API base URL lives in config/storage, never hardcoded. The contract is defined in `SPEC.md`.
- Never use the word "compliance" in UI copy — say "issues", "monitoring", "regression alerts".
