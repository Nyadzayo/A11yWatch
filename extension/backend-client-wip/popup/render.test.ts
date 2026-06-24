import { describe, expect, it } from 'vitest'

import type { ImpactGroup } from '../lib/audit'
import { escapeHtml, renderGroupsHtml, summaryLine } from './render'

function v(over: Record<string, unknown> = {}): any {
  return {
    id: '1',
    scan_id: 's',
    page_url: 'https://x/a',
    rule_id: 'image-alt',
    impact: 'serious',
    help: 'Images must have alt text',
    help_url: 'https://deque.test/image-alt',
    target: 'img',
    html_snippet: null,
    fingerprint: 'fp',
    ...over,
  }
}

describe('escapeHtml', () => {
  it('escapes HTML metacharacters', () => {
    expect(escapeHtml(`<a href="x">&'`)).toBe('&lt;a href=&quot;x&quot;&gt;&amp;&#39;')
  })
})

describe('summaryLine', () => {
  it('pluralizes and reports new/resolved counts', () => {
    expect(summaryLine(9, 3, 2)).toBe('9 issues · 3 new · 2 resolved')
    expect(summaryLine(1, 1, 0)).toBe('1 issue · 1 new · 0 resolved')
  })
})

describe('renderGroupsHtml', () => {
  it('renders rule, help link, and impact heading with count', () => {
    const groups: ImpactGroup[] = [{ impact: 'serious', violations: [v()] }]
    const html = renderGroupsHtml(groups)
    expect(html).toContain('image-alt')
    expect(html).toContain('https://deque.test/image-alt')
    expect(html).toContain('serious (1)')
  })

  it('escapes injected content (no XSS via rule/help/target)', () => {
    const html = renderGroupsHtml([{ impact: 'minor', violations: [v({ rule_id: '<script>x' })] }])
    expect(html).not.toContain('<script>x')
    expect(html).toContain('&lt;script&gt;x')
  })

  it('shows an empty state when there are no groups', () => {
    expect(renderGroupsHtml([])).toContain('No issues')
  })

  it('only links http(s) help URLs (blocks javascript: scheme)', () => {
    const html = renderGroupsHtml([
      { impact: 'serious', violations: [v({ help_url: 'javascript:alert(1)' })] },
    ])
    expect(html).not.toContain('javascript:alert(1)')
    expect(html).not.toContain('<a')
  })

  it('never emits the forbidden word "compliance"', () => {
    const html = renderGroupsHtml([{ impact: 'serious', violations: [v()] }]) + summaryLine(1, 1, 0)
    expect(html.toLowerCase()).not.toContain('compliance')
  })
})
