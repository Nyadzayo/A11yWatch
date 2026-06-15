import { escapeHtml } from '../lib/escape'
import { fixForNode } from '../lib/fixmap'
import { IMPACT_ORDER, sortBySeverity, type SeverityCounts } from '../lib/severity'
import type { Impact, Issue } from '../lib/types'

function impactLabel(impact: Impact | null): string {
  return impact ? impact[0].toUpperCase() + impact.slice(1) : 'Unknown'
}

function impactClass(impact: Impact | null): string {
  return impact ?? 'unknown'
}

function elementCount(n: number): string {
  return `${n} element${n === 1 ? '' : 's'}`
}

function learnMore(issue: Issue): string {
  const url = issue.helpUrl
  if (!url || !/^https?:\/\//.test(url)) return ''
  return `<a class="action action-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Learn more</a>`
}

function elementsList(issue: Issue): string {
  if (issue.nodes.length <= 1) return ''
  const items = issue.nodes
    .map((n) => `<li><code>${escapeHtml(n.target)}</code></li>`)
    .join('')
  return `<ul class="issue-elements">${items}</ul>`
}

/** One expandable issue card. `index` is the position in the severest-first list and is
 *  used by the popup to look the issue up for highlight/copy. */
export function renderIssueCard(issue: Issue, index: number): string {
  const impact = impactClass(issue.impact)
  const firstSelector = issue.nodes[0]?.target ?? ''
  const fix = issue.nodes.length ? fixForNode(issue, issue.nodes[0]) : issue.description
  return `<li class="issue" data-index="${index}">
  <details class="issue-details">
    <summary class="issue-summary">
      <span class="issue-main">
        <span class="issue-title">${escapeHtml(issue.help)}</span>
        ${firstSelector ? `<code class="issue-selector">${escapeHtml(firstSelector)}</code>` : ''}
      </span>
      <span class="issue-side">
        <span class="badge badge-${impact}">${escapeHtml(impactLabel(issue.impact))}</span>
        <span class="issue-count">${elementCount(issue.nodes.length)}</span>
      </span>
    </summary>
    <div class="issue-body">
      <div class="fix">
        <span class="fix-label">How to fix</span>
        <p class="fix-text">${escapeHtml(fix)}</p>
      </div>
      ${elementsList(issue)}
      <div class="issue-actions">
        <button type="button" class="action" data-action="highlight" data-index="${index}">Highlight</button>
        <button type="button" class="action" data-action="copy" data-index="${index}">Copy for ticket</button>
        ${learnMore(issue)}
      </div>
    </div>
  </details>
</li>`
}

/** The full issues list, or the empty/success state. Renders in the given order and assigns
 *  `data-index` by position — callers must pass the list already in display order
 *  (the popup pre-sorts via `sortBySeverity`), so the rendered index space is the single
 *  source of truth the popup looks card actions up against. */
export function renderIssues(issues: Issue[]): string {
  if (issues.length === 0) return renderEmptyState()
  const cards = issues.map((issue, i) => renderIssueCard(issue, i)).join('\n')
  return `<ul class="issue-list">${cards}</ul>`
}

/** Severity breakdown chips — one per non-zero severity. Each is a toggle filter
 *  (pressed = shown); the popup wires the clicks. */
export function renderBreakdown(counts: SeverityCounts): string {
  return IMPACT_ORDER.filter((impact) => counts[impact] > 0)
    .map(
      (impact) =>
        `<button type="button" class="badge badge-${impact} filter-chip" data-severity="${impact}" aria-pressed="true">${impactLabel(impact)} ${counts[impact]}</button>`,
    )
    .join('')
}

/** Needs-review (axe incomplete) list — informational, no score impact. */
export function renderNeedsReview(issues: Issue[]): string {
  if (issues.length === 0) {
    return `<p class="empty-note">Nothing needs manual review on this page.</p>`
  }
  const items = sortBySeverity(issues)
    .map((issue) => {
      const selector = issue.nodes[0]?.target ?? ''
      const why = issue.nodes[0]?.failureSummary ?? issue.description
      return `<li class="review-item">
  <div class="issue-title">${escapeHtml(issue.help)}</div>
  ${selector ? `<code class="issue-selector">${escapeHtml(selector)}</code>` : ''}
  <p class="review-why">${escapeHtml(why)}</p>
</li>`
    })
    .join('\n')
  return `<p class="review-intro">axe can’t decide these automatically — check them by hand.</p>
<ul class="review-list">${items}</ul>`
}

/** Shown when a scan finds no automatically-detectable issues. */
export function renderEmptyState(): string {
  return `<div class="empty-state">
  <p class="empty-title">No automatically detectable issues found.</p>
  <p class="empty-sub">Nice — but automated scanning can't catch everything. Keyboard use,
    focus order, meaningful alt text and screen-reader flow still need a human check.</p>
</div>`
}

export { escapeHtml }
