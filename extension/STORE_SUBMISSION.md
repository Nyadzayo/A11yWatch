# Chrome Web Store submission — A11yTrail — Accessibility Checker

Everything a reviewer/listing needs. This build is **fully client-side**: it runs axe-core in
your browser, makes **no network requests**, and **collects no data**.

---

## Listing

- **Name:** A11yTrail — Accessibility Checker (WCAG & ADA)
- **Short description (≤132 chars):**
  Free WCAG & ADA accessibility checker — scan any page for issues, get fix guidance and WCAG
  references. Runs locally.
- **Category:** Developer Tools (alternative: Accessibility)
- **Language:** English

### Detailed description
> A11yTrail is a free, one-click WCAG & ADA accessibility checker for the page you're on. Click the toolbar
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
> Everything happens on your device. A11yTrail makes no network requests and collects no
> data — nothing about the pages you scan ever leaves your browser.
>
> Automated testing catches many issues but can't catch everything (keyboard use, focus
> order, meaningful alt text and screen-reader flow still need a human) — A11yTrail is here
> to make the automatable part fast.

> Note: deliberately avoids "compliance/guarantee" claims — it surfaces issues and guidance,
> it does not certify conformance.

---

## Permission justifications

Only **two** permissions are requested. No `host_permissions`, no `<all_urls>`, no `tabs`,
no `storage`, no `downloads`.

- **`activeTab`** — Used only when you click the A11yTrail toolbar button. It grants
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

- **Privacy policy URL:** https://nyadzayo.github.io/A11yTrail/privacy-policy.html
- **Single purpose:** Check the current web page for WCAG & ADA accessibility issues and show
  how to fix them.

---

## Store assets (ready to upload — in `store-assets/`)

All produced at the exact pixel sizes the Web Store requires. Upload these in the
**Store listing** tab of the Developer Dashboard.

| File | Size | Dashboard field |
|---|---|---|
| `icons/icon128.png` | 128×128 | **Store icon** (also the action icon, already in the manifest) |
| `store-assets/screenshot-1-results.png` | 1280×800 | **Screenshot 1** — severity-ranked results + score |
| `store-assets/screenshot-2-fix.png` | 1280×800 | **Screenshot 2** — expanded "How to fix" + copy-for-ticket |
| `store-assets/screenshot-3-empty.png` | 1280×800 | **Screenshot 3** — honest clean-scan state |
| `store-assets/promo-small.png` | 440×280 | **Small promo tile** (store grid / search) |
| `store-assets/promo-marquee.png` | 1400×560 | **Marquee promo tile** (only needed if featured) |

At least one 1280×800 (or 640×400) screenshot is **required**; the promo tiles are optional
but recommended. The `.html` next to each PNG is the editable source — re-export with the
steps in `store-assets/README.md`.

---

## Manifest V3 compliance (why this passes review)

- **Single purpose** — one job: check the current page for accessibility issues. No bundled
  unrelated features.
- **Least privilege** — permissions are exactly `["activeTab","scripting"]`. No
  `host_permissions`, `<all_urls>`, `tabs`, `storage`, `downloads`, or
  `web_accessible_resources`. `activeTab` is granted only on the user's click.
- **No remotely hosted code** — axe-core is bundled in the package and injected from disk via
  `chrome.scripting`; the extension fetches nothing at runtime (the bundle has zero
  `fetch`/`XMLHttpRequest`). This is the #1 MV3 rejection cause and we avoid it outright.
- **CSP-clean** — no inline scripts, no inline event handlers, no `eval`/`new Function` in the
  first-party bundle. (axe-core's internal `new Function` runs in the *page* world, not the
  extension context — see Third-party note above.)
- **Permissions justified in-listing** — see the justifications section; each maps directly to
  a user-visible feature (scan = scripting, current tab = activeTab).
- **Honest claims** — no "guarantee compliance"/"become ADA compliant" language; copy says it
  *finds and documents* issues and explicitly notes automation can't catch everything.
- **Privacy** — collects nothing; data-disclosure form answered "No" across the board; privacy
  policy URL provided.

---

## Submission walkthrough (Chrome Web Store Developer Dashboard)

1. Register/confirm a Chrome Web Store **developer account** (one-time US$5 fee) — *you must do
   this; it requires a Google sign-in I can't perform.*
2. **Build the upload zip:** `cd extension && npm run package` → produces
   `a11ytrail-extension-v0.1.0.zip` (contents of `dist/`, `manifest.json` at root).
3. Dashboard → **Add new item** → upload the zip.
4. **Store listing** tab: paste the Name, Summary, and Detailed description (above), set
   **Category = Developer Tools**, language English, and upload the assets from the table.
5. **Privacy** tab: set the single-purpose description, add a justification for **each**
   permission (`activeTab`, `scripting`) and confirm **no** remote code; complete the data
   practices form (all **No**) and the three certifications; paste the privacy policy URL.
6. **Distribution:** Public (or Unlisted to soft-launch). Save draft → **Submit for review**.

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
npm run package    # zips dist/ -> a11ytrail-extension-v<version>.zip for upload
```

Upload `a11ytrail-extension-v0.1.0.zip` (a zip of the **contents** of `dist/`, with
`manifest.json` at the root).

### Pre-submission checklist
- [ ] `dist/manifest.json` permissions are exactly `["activeTab","scripting"]`.
- [ ] `dist/axe.min.js` is present (bundled axe-core) and nothing is fetched at runtime
      (`grep -rE "fetch\(|XMLHttpRequest" dist/assets` → empty).
- [ ] Popup loads on a normal page; restricted pages (chrome://, web store, PDFs) show the
      graceful "can't be scanned" state.
- [ ] All 6 store assets present at exact sizes (128×128, 1280×800 ×3, 440×280, 1400×560).
- [ ] Listing copy contains **no** "guarantee/compliant/certify" claims.
- [ ] A justification entered for **each** permission + "uses remote code? **No**".
- [ ] Data-practices form all **No** + 3 certifications checked.
- [ ] **Privacy policy URL resolves** — `https://nyadzayo.github.io/A11yTrail/privacy-policy.html`
      only works after the GitHub repo is renamed to **A11yTrail** and Pages is enabled. Do this
      before submitting, or the listing will be rejected for a dead privacy URL.
