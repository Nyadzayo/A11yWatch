# Chrome Web Store submission — A11yWatch — Accessibility Checker

Everything a reviewer/listing needs. This build is **fully client-side**: it runs axe-core in
your browser, makes **no network requests**, and **collects no data**.

---

## Listing

- **Name:** A11yWatch — Accessibility Checker
- **Short description (≤132 chars):**
  Scan any web page for accessibility issues with axe-core — severity, fixes and WCAG
  references, all locally in your browser.
- **Category:** Developer Tools (alternative: Accessibility)
- **Language:** English

### Detailed description
> A11yWatch is a one-click accessibility checker for the page you're on. Click the toolbar
> icon and it runs the open-source axe-core engine **locally in your browser** to find
> accessibility issues — then shows you a severity-weighted score, a breakdown by severity,
> and a sorted list of issues.
>
> For each issue you get plain-language "How to fix" guidance, a "Learn more" link to the
> rule's documentation, a one-click "Copy for ticket" for your bug tracker, and a "Highlight"
> action that outlines the affected element on the page. Filter by severity or WCAG level
> (A / AA / AAA), review the "Needs review" items axe can't decide automatically, and export
> the results as an HTML report or JSON.
>
> Everything happens on your device. A11yWatch makes no network requests and collects no
> data — nothing about the pages you scan ever leaves your browser.
>
> Automated testing catches many issues but can't catch everything (keyboard use, focus
> order, meaningful alt text and screen-reader flow still need a human) — A11yWatch is here
> to make the automatable part fast.

> Note: deliberately avoids "compliance/guarantee" claims — it surfaces issues and guidance,
> it does not certify conformance.

---

## Permission justifications

Only **two** permissions are requested. No `host_permissions`, no `<all_urls>`, no `tabs`,
no `storage`, no `downloads`.

- **`activeTab`** — Used only when you click the A11yWatch toolbar button. It grants
  temporary access to the **current tab** so the extension can analyze the page you're
  looking at. It does not grant access to other tabs, and it conveys no access to your
  browsing history.
- **`scripting`** — Used to inject the **bundled** axe-core analyzer into the current tab to
  run the accessibility checks locally, and to draw/remove a highlight outline on an element
  when you click "Highlight". All injected code is packaged in the extension
  (`axe.min.js`); nothing is fetched from a remote server.

---

## Data disclosure (Privacy practices tab)

- **Does this item collect or use user data?** No.
- Personally identifiable information — **No**
- Health information — **No**
- Financial / payment information — **No**
- Authentication information — **No**
- Personal communications — **No**
- Location — **No**
- Web history — **No**
- User activity — **No**
- Website content — **No** (page content is analyzed in-memory on your device and is never
  transmitted or stored)

Certifications:
- I do **not** sell or transfer user data to third parties.
- I do **not** use or transfer user data for purposes unrelated to the item's single purpose.
- I do **not** use or transfer user data to determine creditworthiness or for lending.

- **Privacy policy URL:** https://a11ywatch.com/privacy-policy
- **Single purpose:** Check the current web page for accessibility issues and show how to
  fix them.

---

## Screenshots to capture (1280×800)

1. **Populated results** — score ring + "issues found", severity breakdown chips, the
   severity-sorted issue list (Issues tab active, "WCAG 2.1 AA" label).
2. **Expanded "How to fix"** — one issue card open showing the fix guidance, the element
   selector(s), and the Highlight / Copy for ticket / Learn more actions.
3. **Empty / success state** — the "No automatically detectable issues found" panel with the
   honest "automated scanning can't catch everything" note.
4. *(optional)* **Needs review tab** — the axe `incomplete` items, to show they're separate
   from the headline count.
5. *(optional)* **Export menu** — Download HTML report / Download JSON / Copy summary.

---

## Third-party / open-source

- **axe-core 4.12.1** (Deque Systems) — Mozilla Public License 2.0. Bundled at
  `public/axe.min.js` → ships as `axe.min.js` at the package root; injected locally via
  `chrome.scripting`, never fetched remotely. Pin/update with `npm run copy-axe`.
  - *Reviewer note:* axe-core's minified source contains a few `new Function(...)` calls.
    These run in the **scanned page's** world (where the analyzer is injected), **not** in the
    extension's privileged popup context, so they do not violate the popup's MV3 CSP. The
    first-party extension bundle contains **zero** `eval`/`new Function` and makes no network
    requests.

- **Fonts.** The popup uses the marketing font stacks (Fraunces display / Hanken Grotesk
  body) but **does not load any web fonts** — to keep the package network-free it falls back
  to system fonts (Georgia serif / system sans) where those faces aren't installed. The brand
  is carried by the palette and the eye icon. If pixel-exact typography is wanted later, the
  fonts (both SIL OFL) can be vendored locally as `woff2`.

---

## Build & package

```bash
cd extension
npm install
npm run icons      # regenerate icons/ (only needed if the icon changes)
npm test           # 43 unit tests (score, severity, fix-map, incomplete-exclusion, …)
npm run typecheck
npm run build      # vite build -> dist/ (runs copy-axe first)
npm run package    # zips dist/ -> a11ywatch-extension-v<version>.zip for upload
```

Upload `a11ywatch-extension-v0.1.0.zip` (a zip of the **contents** of `dist/`, with
`manifest.json` at the root).

### Pre-submission checklist
- [ ] `dist/manifest.json` permissions are exactly `["activeTab","scripting"]`.
- [ ] `dist/axe.min.js` is present (bundled axe-core).
- [ ] No `fetch`/network calls in `dist/assets/*.js` (the extension makes zero requests).
- [ ] Popup loads on a normal page; restricted pages (chrome://, web store, PDFs) show the
      graceful "can't be scanned" state.
- [ ] Privacy policy is live at the URL above before publishing.
