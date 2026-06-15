// Bridge between the popup and the page: inject the BUNDLED axe-core, run it, and
// draw/clear on-page highlights — all via chrome.scripting (activeTab + scripting only,
// no host permissions, no network). The injected functions are self-contained: they must
// reference ONLY their parameters and page globals (window/document), never module scope,
// because chrome serializes them with `.toString()` and runs them in the page world.

import type { AxeResults } from '../lib/types'
import { ACTIVE_AXE_TAGS } from '../lib/wcag'

const OVERLAY_ATTR = 'data-a11ywatch-overlay'

/** URLs we cannot script (restricted schemes + the Web Store). */
export function isScannableUrl(url: string | undefined): boolean {
  if (!url) return false
  if (!/^https?:\/\//i.test(url)) return false
  return !/^https?:\/\/(chrome\.google\.com\/webstore|chromewebstore\.google\.com)/i.test(url)
}

/** Runs in the page. Executes axe with the given tag set and returns a lean result. */
function runAxeInPage(tags: string[]): unknown {
  const w = window as unknown as { axe?: { run: (ctx: Document, opts: unknown) => Promise<unknown> } }
  if (!w.axe) return { error: 'axe-core was not injected' }
  function lean(items: any[]) {
    return items.map(function (it: any) {
      return {
        id: it.id,
        impact: it.impact,
        tags: it.tags,
        description: it.description,
        help: it.help,
        helpUrl: it.helpUrl,
        nodes: (it.nodes || []).map(function (n: any) {
          return { target: n.target, html: n.html, failureSummary: n.failureSummary }
        }),
      }
    })
  }
  return w.axe
    .run(document, {
      runOnly: { type: 'tag', values: tags },
      resultTypes: ['violations', 'incomplete', 'passes', 'inapplicable'],
    })
    .then(function (r: any) {
      return {
        violations: lean(r.violations),
        incomplete: lean(r.incomplete),
        passCount: r.passes.length,
        inapplicableCount: r.inapplicable.length,
      }
    })
    .catch(function (e: unknown) {
      return { error: String(e) }
    })
}

/** Runs in the page. Outlines each selector with a removable overlay; scrolls to the first. */
function highlightInPage(selectors: string[], attr: string): boolean {
  document.querySelectorAll('[' + attr + ']').forEach(function (el) {
    el.remove()
  })
  let first: Element | null = null
  selectors.forEach(function (sel) {
    let node: Element | null = null
    try {
      node = document.querySelector(sel)
    } catch (e) {
      node = null
    }
    if (!node) return
    if (!first) first = node
    const r = node.getBoundingClientRect()
    const o = document.createElement('div')
    o.setAttribute(attr, '')
    o.style.cssText =
      'position:absolute;z-index:2147483646;pointer-events:none;box-sizing:border-box;' +
      'border:2px solid #e11d48;border-radius:3px;background:rgba(225,29,72,0.12);' +
      'top:' +
      (r.top + window.scrollY - 2) +
      'px;left:' +
      (r.left + window.scrollX - 2) +
      'px;width:' +
      (r.width + 4) +
      'px;height:' +
      (r.height + 4) +
      'px;'
    document.body.appendChild(o)
  })
  if (first) (first as Element).scrollIntoView({ behavior: 'smooth', block: 'center' })
  return !!first
}

/** Runs in the page. Removes every overlay we added. */
function clearHighlightsInPage(attr: string): void {
  document.querySelectorAll('[' + attr + ']').forEach(function (el) {
    el.remove()
  })
}

/** Inject bundled axe, run it, and return normalized-ready results. Throws on restricted pages. */
export async function scanTab(tabId: number): Promise<AxeResults> {
  await chrome.scripting.executeScript({ target: { tabId }, files: ['axe.min.js'] })
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: runAxeInPage,
    args: [ACTIVE_AXE_TAGS],
  })
  const r = result as
    | { violations: AxeResults['violations']; incomplete: AxeResults['incomplete']; passCount: number; inapplicableCount: number }
    | { error: string }
  if (!r || 'error' in r) throw new Error((r as { error?: string })?.error ?? 'Scan failed')
  return {
    violations: r.violations,
    incomplete: r.incomplete,
    passes: new Array(r.passCount).fill(null),
    inapplicable: new Array(r.inapplicableCount).fill(null),
  }
}

export async function highlightOnTab(tabId: number, selectors: string[]): Promise<void> {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: highlightInPage,
    args: [selectors, OVERLAY_ATTR],
  })
}

export async function clearHighlightsOnTab(tabId: number): Promise<void> {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: clearHighlightsInPage,
    args: [OVERLAY_ATTR],
  })
}
