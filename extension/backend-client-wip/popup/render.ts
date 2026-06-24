import type { ImpactGroup } from '../lib/audit'

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ESCAPES[c])
}

function isHttpUrl(url: string | null): url is string {
  return !!url && (url.startsWith('http://') || url.startsWith('https://'))
}

export function summaryLine(total: number, newCount: number, resolved: number): string {
  const noun = total === 1 ? 'issue' : 'issues'
  return `${total} ${noun} · ${newCount} new · ${resolved} resolved`
}

export function renderGroupsHtml(groups: ImpactGroup[]): string {
  if (groups.length === 0) return '<p class="empty">No issues found on this page 🎉</p>'
  return groups
    .map((group) => {
      const impact = escapeHtml(group.impact)
      const items = group.violations
        .map((v) => {
          const help = v.help ? `<span class="help">${escapeHtml(v.help)}</span>` : ''
          const learn = isHttpUrl(v.help_url)
            ? `<a class="learn" href="${escapeHtml(v.help_url)}" target="_blank" rel="noopener noreferrer">Learn more</a>`
            : ''
          const target = v.target ? `<code class="target">${escapeHtml(v.target)}</code>` : ''
          return `<li class="issue impact-${impact}"><span class="rule">${escapeHtml(v.rule_id)}</span>${help}${target}${learn}</li>`
        })
        .join('')
      return `<section class="group"><h3 class="impact ${impact}">${impact} (${group.violations.length})</h3><ul>${items}</ul></section>`
    })
    .join('')
}
