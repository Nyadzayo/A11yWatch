import { normalizeAxeResults } from '../lib/normalize'
import { scoreFor } from '../lib/score'
import { severityCounts, sortBySeverity } from '../lib/severity'
import { ticketText, exportHtml, exportJson } from '../lib/format'
import type { Issue, ScanData } from '../lib/types'
import { filterByLevel, standardLabel, type WcagLevel } from '../lib/wcag'
import { clearHighlightsOnTab, highlightOnTab, isScannableUrl, scanTab } from '../scan/inject'
import { renderBreakdown, renderIssues, renderNeedsReview } from './render'

function el<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T
}

const STATES = ['state-scanning', 'state-unsupported', 'state-error', 'state-results'] as const
type StateId = (typeof STATES)[number]

let tabId: number | null = null
let scan: ScanData | null = null
let rendered: Issue[] = [] // issues currently shown — index space for the card actions
let level: WcagLevel = 'AA'
const activeSeverities = new Set<string>() // severities currently shown
let highlightedIndex: number | null = null

function showState(id: StateId): void {
  for (const s of STATES) el(s).hidden = s !== id
  el('footer').hidden = id !== 'state-results'
}

async function getActiveTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  return tab
}

async function runScan(): Promise<void> {
  if (tabId == null) return
  showState('state-scanning')
  highlightedIndex = null
  try {
    const raw = await scanTab(tabId)
    const tab = await getActiveTab()
    scan = normalizeAxeResults(raw, tab?.url ?? '')
    for (const impact of ['critical', 'serious', 'moderate', 'minor', 'unknown']) {
      activeSeverities.add(impact)
    }
    renderResults()
    showState('state-results')
  } catch (err) {
    el('error-message').textContent =
      err instanceof Error ? err.message : 'Something went wrong while scanning.'
    showState('state-error')
  }
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname || url
  } catch {
    return url
  }
}

function renderResults(): void {
  if (!scan) return
  const counts = severityCounts(scan.issues)
  const score = scoreFor(scan.issues)

  const ring = el('score-ring')
  ring.className = `score-ring grade-${score.grade}`
  ring.setAttribute(
    'aria-label',
    `Accessibility score ${score.value} out of 100, grade ${score.grade}`,
  )
  el('score-grade').textContent = score.grade
  el('score-value').textContent = `${score.value}`
  const total = scan.issues.length
  el('issue-count').textContent = `${total} issue${total === 1 ? '' : 's'} found`
  el('host').textContent = hostOf(scan.url)
  el('active-standard').textContent = standardLabel(level)

  el('breakdown').innerHTML = renderBreakdown(counts)
  el('review-tab-count').textContent = `${scan.needsReview.length}`
  el('panel-review').innerHTML = renderNeedsReview(scan.needsReview)

  renderIssuePanel()
}

function renderIssuePanel(): void {
  if (!scan || tabId == null) return
  // Changing the list invalidates any on-page highlight — clear it so nothing is left behind.
  void clearHighlightsOnTab(tabId)
  highlightedIndex = null

  const byLevel = filterByLevel(scan.issues, level)
  const visible = sortBySeverity(
    byLevel.filter((i) => activeSeverities.has(i.impact ?? 'unknown')),
  )
  rendered = visible
  el('issues-tab-count').textContent = `${visible.length}`

  const panel = el('panel-issues')
  if (visible.length === 0 && scan.issues.length > 0) {
    panel.innerHTML = `<p class="empty-note">No issues match the current filters.</p>`
  } else {
    panel.innerHTML = renderIssues(visible)
  }
}

function selectTab(name: 'issues' | 'review'): void {
  const issues = name === 'issues'
  const tabIssues = el('tab-issues')
  const tabReview = el('tab-review')
  tabIssues.setAttribute('aria-selected', String(issues))
  tabReview.setAttribute('aria-selected', String(!issues))
  tabIssues.tabIndex = issues ? 0 : -1
  tabReview.tabIndex = issues ? -1 : 0
  el('panel-issues').hidden = !issues
  el('panel-review').hidden = issues
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Fallback for contexts where the async clipboard API is unavailable.
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    let ok = false
    try {
      ok = document.execCommand('copy')
    } catch {
      ok = false
    }
    ta.remove()
    return ok
  }
}

function download(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function flash(button: HTMLElement, message: string, revertTo: string): void {
  button.textContent = message
  setTimeout(() => {
    button.textContent = revertTo
  }, 1400)
}

async function onIssueAction(event: MouseEvent): Promise<void> {
  const button = (event.target as HTMLElement).closest<HTMLElement>('button[data-action]')
  if (!button || tabId == null) return
  const index = Number(button.dataset.index)
  const issue = rendered[index]
  if (!issue) return

  if (button.dataset.action === 'copy') {
    const ok = await copyText(ticketText(issue))
    flash(button, ok ? 'Copied' : 'Copy failed', 'Copy for ticket')
    return
  }

  if (button.dataset.action === 'highlight') {
    if (highlightedIndex === index) {
      await clearHighlightsOnTab(tabId)
      highlightedIndex = null
      button.textContent = 'Highlight'
      button.classList.remove('is-active')
      return
    }
    const selectors = issue.nodes.map((n) => n.target).filter(Boolean)
    // reset the previously active highlight button, if it is still on screen
    el('panel-issues')
      .querySelectorAll<HTMLElement>('button[data-action="highlight"].is-active')
      .forEach((b) => {
        b.textContent = 'Highlight'
        b.classList.remove('is-active')
      })
    await highlightOnTab(tabId, selectors)
    highlightedIndex = index
    button.textContent = 'Hide highlight'
    button.classList.add('is-active')
  }
}

function onBreakdownClick(event: MouseEvent): void {
  const chip = (event.target as HTMLElement).closest<HTMLElement>('.filter-chip')
  if (!chip) return
  const severity = chip.dataset.severity
  if (!severity) return
  const pressed = chip.getAttribute('aria-pressed') === 'true'
  chip.setAttribute('aria-pressed', String(!pressed))
  if (pressed) activeSeverities.delete(severity)
  else activeSeverities.add(severity)
  renderIssuePanel()
}

function setupExportMenu(): void {
  const btn = el('export-btn')
  const menu = el('export-menu')
  const items = () => Array.from(menu.querySelectorAll<HTMLElement>('button[data-export]'))
  const close = (returnFocus = false): void => {
    if (menu.hidden) return
    menu.hidden = true
    btn.setAttribute('aria-expanded', 'false')
    if (returnFocus) btn.focus()
  }
  const open = (): void => {
    menu.hidden = false
    btn.setAttribute('aria-expanded', 'true')
    items()[0]?.focus() // move focus into the menu so it is keyboard-operable
  }
  btn.addEventListener('click', (e) => {
    e.stopPropagation()
    if (menu.hidden) open()
    else close()
  })
  btn.addEventListener('keydown', (e) => {
    if ((e as KeyboardEvent).key === 'ArrowDown' && menu.hidden) {
      e.preventDefault()
      open()
    }
  })
  menu.addEventListener('keydown', (event) => {
    const e = event as KeyboardEvent
    const list = items()
    const idx = list.indexOf(document.activeElement as HTMLElement)
    if (e.key === 'Escape') {
      e.preventDefault()
      close(true) // return focus to the trigger
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      list[(idx + 1) % list.length]?.focus()
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      list[(idx - 1 + list.length) % list.length]?.focus()
    } else if (e.key === 'Home') {
      e.preventDefault()
      list[0]?.focus()
    } else if (e.key === 'End') {
      e.preventDefault()
      list[list.length - 1]?.focus()
    }
  })
  menu.addEventListener('click', async (event) => {
    const item = (event.target as HTMLElement).closest<HTMLElement>('button[data-export]')
    if (!item || !scan) return
    const host = hostOf(scan.url) || 'page'
    if (item.dataset.export === 'html') {
      download(`a11ytrail-${host}.html`, exportHtml(scan), 'text/html')
    } else if (item.dataset.export === 'json') {
      download(`a11ytrail-${host}.json`, exportJson(scan), 'application/json')
    } else if (item.dataset.export === 'copy') {
      const ok = await copyText(exportJson(scan))
      flash(item, ok ? 'Copied' : 'Copy failed', 'Copy summary')
      return
    }
    close(true)
  })
  document.addEventListener('click', () => close())
}

function setupTabs(): void {
  el('tab-issues').addEventListener('click', () => selectTab('issues'))
  el('tab-review').addEventListener('click', () => selectTab('review'))
  const tablist = document.querySelector('.tablist')
  tablist?.addEventListener('keydown', (event) => {
    const e = event as KeyboardEvent
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    e.preventDefault()
    const toReview = e.key === 'ArrowRight'
    selectTab(toReview ? 'review' : 'issues')
    el(toReview ? 'tab-review' : 'tab-issues').focus()
  })
}

async function init(): Promise<void> {
  setupTabs()
  setupExportMenu()
  el('breakdown').addEventListener('click', onBreakdownClick)
  el('panel-issues').addEventListener('click', (e) => void onIssueAction(e as MouseEvent))
  el('rescan').addEventListener('click', () => void runScan())
  el('retry').addEventListener('click', () => void runScan())
  el<HTMLSelectElement>('level-select').addEventListener('change', (e) => {
    level = (e.target as HTMLSelectElement).value as WcagLevel
    el('active-standard').textContent = standardLabel(level)
    renderIssuePanel()
  })

  const tab = await getActiveTab()
  if (!tab || tab.id == null || !isScannableUrl(tab.url)) {
    showState('state-unsupported')
    return
  }
  tabId = tab.id
  await runScan()
}

void init()
