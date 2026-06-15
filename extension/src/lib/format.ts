import { escapeHtml } from './escape'
import { fixForNode } from './fixmap'
import { scoreFor } from './score'
import { severityCounts } from './severity'
import type { Issue, ScanData } from './types'
import { standardLabel, wcagLevel } from './wcag'

function impactLabel(issue: Issue): string {
  return issue.impact ? issue.impact[0].toUpperCase() + issue.impact.slice(1) : 'Unknown'
}

function levelLine(issue: Issue): string | null {
  const level = wcagLevel(issue.tags)
  return level ? standardLabel(level) : null
}

/** A plain-text block to paste into a bug tracker for one issue. */
export function ticketText(issue: Issue): string {
  const lines = [
    `[A11yTrail] ${issue.help}`,
    `Rule: ${issue.ruleId} (${impactLabel(issue)})`,
  ]
  const std = levelLine(issue)
  if (std) lines.push(`Standard: ${std}`)
  lines.push(`Affected elements (${issue.nodes.length}):`)
  for (const node of issue.nodes) lines.push(`  - ${node.target}`)
  if (issue.nodes.length > 0) lines.push(`Fix: ${fixForNode(issue, issue.nodes[0])}`)
  if (issue.helpUrl) lines.push(`Learn more: ${issue.helpUrl}`)
  return lines.join('\n')
}

interface ExportSummary {
  url: string
  total: number
  critical: number
  serious: number
  moderate: number
  minor: number
  score: number
  grade: string
  passes: number
  inapplicable: number
}

function summaryOf(scan: ScanData): ExportSummary {
  const counts = severityCounts(scan.issues)
  const score = scoreFor(scan.issues)
  return {
    url: scan.url,
    total: counts.total,
    critical: counts.critical,
    serious: counts.serious,
    moderate: counts.moderate,
    minor: counts.minor,
    score: score.value,
    grade: score.grade,
    passes: scan.passCount,
    inapplicable: scan.inapplicableCount,
  }
}

/** A machine-readable export of the whole scan. */
export function exportJson(scan: ScanData): string {
  return JSON.stringify(
    {
      url: scan.url,
      tool: 'A11yTrail extension (axe-core)',
      summary: summaryOf(scan),
      issues: scan.issues,
      needsReview: scan.needsReview,
    },
    null,
    2,
  )
}

/** A standalone, shareable HTML report of the scan (fully client-side, no assets). */
export function exportHtml(scan: ScanData): string {
  const s = summaryOf(scan)
  const issueRows = scan.issues
    .map((issue) => {
      const level = levelLine(issue)
      const elements = issue.nodes
        .map((n) => `<li><code>${escapeHtml(n.target)}</code></li>`)
        .join('')
      const fix = issue.nodes.length ? escapeHtml(fixForNode(issue, issue.nodes[0])) : ''
      return `<article class="issue ${escapeHtml(issue.impact ?? 'unknown')}">
  <h3>${escapeHtml(issue.help)}</h3>
  <p class="meta">${escapeHtml(issue.ruleId)} · ${escapeHtml(impactLabel(issue))}${
    level ? ` · ${escapeHtml(level)}` : ''
  }</p>
  <p class="fix">${fix}</p>
  <ul class="elements">${elements}</ul>
</article>`
    })
    .join('\n')

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Accessibility report — ${escapeHtml(s.url)}</title>
<style>
  body { font: 14px/1.5 system-ui, sans-serif; max-width: 820px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 20px; }
  .summary { color: #555; }
  .issue { border: 1px solid #e5e7eb; border-left-width: 4px; border-radius: 6px; padding: 12px 16px; margin: 12px 0; }
  .issue.critical { border-left-color: #b91c1c; }
  .issue.serious { border-left-color: #c2410c; }
  .issue.moderate { border-left-color: #a16207; }
  .issue.minor { border-left-color: #4b5563; }
  .meta { color: #666; font-size: 12px; margin: 2px 0 8px; }
  code { font-family: ui-monospace, monospace; background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }
  .elements { margin: 6px 0 0; }
  .note { color: #666; font-size: 12px; margin-top: 2rem; }
</style>
</head>
<body>
  <h1>Accessibility report</h1>
  <p class="summary"><strong>${escapeHtml(s.url)}</strong><br>
    Score ${s.score}/100 (${escapeHtml(s.grade)}) · ${s.total} issues —
    ${s.critical} critical, ${s.serious} serious, ${s.moderate} moderate, ${s.minor} minor</p>
  ${issueRows || '<p>No automatically detectable issues found.</p>'}
  <p class="note">Automated scanning with axe-core catches many issues but cannot catch
    everything — manual review is still needed.</p>
</body>
</html>`
}
