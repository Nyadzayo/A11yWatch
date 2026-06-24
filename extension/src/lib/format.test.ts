import { describe, expect, it } from 'vitest'
import { exportHtml, exportJson, ticketText } from './format'
import type { Issue, ScanData } from './types'

function issue(over: Partial<Issue> = {}): Issue {
  return {
    ruleId: 'image-alt',
    impact: 'critical',
    help: 'Images must have alternate text',
    description: 'Ensures img elements have alternate text',
    helpUrl: 'https://dequeuniversity.com/rules/axe/4.12/image-alt',
    tags: ['wcag2a', 'wcag111'],
    nodes: [{ target: 'img.hero', html: '<img class="hero">', failureSummary: 'add alt' }],
    ...over,
  }
}

function scan(over: Partial<ScanData> = {}): ScanData {
  return {
    url: 'https://acme.test/',
    issues: [issue()],
    needsReview: [],
    passCount: 12,
    inapplicableCount: 3,
    ...over,
  }
}

describe('ticketText', () => {
  it('includes the rule, title, selector, WCAG level and help URL', () => {
    const text = ticketText(issue())
    expect(text).toContain('image-alt')
    expect(text).toContain('Images must have alternate text')
    expect(text).toContain('img.hero')
    expect(text).toContain('WCAG 2.1 A')
    expect(text).toContain('https://dequeuniversity.com/rules/axe/4.12/image-alt')
  })

  it('lists every failing element', () => {
    const text = ticketText(
      issue({ nodes: [
        { target: 'img.a', html: '', failureSummary: null },
        { target: 'img.b', html: '', failureSummary: null },
      ] }),
    )
    expect(text).toContain('img.a')
    expect(text).toContain('img.b')
  })
})

describe('exportJson', () => {
  it('produces valid JSON that round-trips the scan', () => {
    const parsed = JSON.parse(exportJson(scan()))
    expect(parsed.url).toBe('https://acme.test/')
    expect(parsed.issues[0].ruleId).toBe('image-alt')
    expect(parsed.summary.total).toBe(1)
  })
})

describe('exportHtml', () => {
  it('is a standalone HTML document naming the page and issues', () => {
    const html = exportHtml(scan())
    expect(html).toContain('<!doctype html>')
    expect(html).toContain('acme.test')
    expect(html).toContain('Images must have alternate text')
  })

  it('escapes issue content so it cannot inject markup', () => {
    const html = exportHtml(scan({ issues: [issue({ help: '<script>x</script>' })] }))
    expect(html).not.toContain('<script>x</script>')
    expect(html).toContain('&lt;script&gt;')
  })
})
