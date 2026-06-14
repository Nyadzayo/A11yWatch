# Extension — A11yWatch (Manifest V3, TypeScript + Vite/CRXJS)

Trigger on-demand accessibility audits of the current tab and show its issues. The background service worker owns all backend calls; the popup is the only UI.

## Layout
- `src/lib/` — pure core (API client, session, audit find-or-create + grouping). Unit-tested.
- `src/background/` — service worker: typed message dispatcher; all network lives here.
- `src/popup/` — Login + Audit views; `render.ts` (pure, tested) builds the issue HTML.

## Commands
- `npm install` · `npm run dev` (watch) · `npm run build` (bundle → `dist/`)
- `npm test` (Vitest — covers `src/lib` + `src/popup/render`) · `npm run typecheck` (`tsc --noEmit`)
- Reload the unpacked `dist/` at `chrome://extensions` after building. The popup DOM/messaging is verified manually (no UI test runner); pure logic is unit-tested instead.

## MV3 gotchas (commonly gotten wrong)
- Service worker is **not** persistent — never hold state in memory; use `chrome.storage`.
- Register all event listeners at the **top level** of the service worker.
- Content scripts run in an isolated world — talk to the worker via `chrome.runtime.sendMessage`.
- Request minimal permissions (`activeTab` + specific host permissions) — never `<all_urls>`.

## Backend contract & copy
- API base URL lives in config/storage, never hardcoded. The contract is defined in `SPEC.md`.
- Never use the word "compliance" in UI copy — say "issues", "monitoring", "regression alerts".
