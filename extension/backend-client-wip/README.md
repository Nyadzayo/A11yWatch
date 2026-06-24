# backend-client-wip (quarantined — not shipped)

This folder holds the **previous backend-coupled extension** (login + session + remote
scan via the A11yWatch API). It is **preserved, not deleted** — it will be wired back up
for the "continuous monitoring" experience **after** the standalone extension is approved
on the Chrome Web Store.

It is intentionally **excluded from the build, typecheck, and tests**:
- `vite build` (CRXJS) only bundles entry points referenced by `manifest.json`.
- `tsconfig.json` `include` is scoped to `src/`.
- `vitest.config.ts` `include` is `src/**/*.test.ts`.

So nothing here ships or runs today. Do not import from `src/` into these files (or vice
versa) until the backend integration is resumed.

## What's here
- `lib/api.ts`, `lib/session.ts`, `lib/config.ts` — backend API client, session storage, base URL.
- `lib/audit.ts` — `findOrCreateProject` / `auditUrl` (remote scan) + the original
  `groupByImpact` (the pure grouping now lives, reimplemented, in `src/lib/severity.ts`).
- `lib/types.ts` — backend DTOs (`Project`, `Scan`, `Violation`, …).
- `background/` — the MV3 service worker + typed network dispatcher.
- `popup/` — the original login + audit popup (HTML/CSS/TS) and its renderer.
- `test/fakes.ts` — in-memory `chrome.storage` fake for the quarantined tests.

## Reviving it later
When the backend is ready post-approval, reintroduce a service worker + the needed
permissions (`storage`, and a host permission for the API origin) behind an explicit,
opt-in "connect to monitoring" flow — and update the store data-disclosure accordingly.
