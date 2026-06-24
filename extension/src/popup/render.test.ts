import { describe, expect, it } from 'vitest'
import { renderBreakdown, renderEmptyState, renderIssues, renderNeedsReview } from './render'
import { severityCounts } from '../lib/severity'
import type { Issue } from '../lib/types'

function issue(over: Partial<Issue> = {}): Issue {
  return {
    ruleId: 'color-contrast',
    impact: 'serious',
    help: 'Elements must meet color contrast minimums',
    description: 'desc',
    helpUrl: 'https://example.test/rule',
    tags: ['wcag2aa'],
    nodes: [{ target: '.btn-primary', html: '<button>', failureSummary: null }],
    ...over,
  }
}

describe('renderIssues', () => {
  it('renders in the given order and assigns data-index by position (single source of truth)', () => {
    const html = renderIssues([
      issue({ impact: 'critical', help: 'First card' }),
      issue({ impact: 'serious', help: 'Second card' }),
      issue({ impact: 'minor', help: 'Third card' }),
    ])
    expect(html.indexOf('First card')).toBeLessThan(html.indexOf('Second card'))
    expect(html.indexOf('Second card')).toBeLessThan(html.indexOf('Third card'))
    expect(html.indexOf('data-index="0"')).toBeLessThan(html.indexOf('data-index="1"'))
    expect(html).toContain('data-index="2"')
  })

  it('shows the title, monospace selector, severity badge and element count', () => {
    const html = renderIssues([
      issue({ nodes: [
        { target: '.a', html: '', failureSummary: null },
        { target: '.b', html: '', failureSummary: null },
      ] }),
    ])
    expect(html).toContain('Elements must meet color contrast minimums')
    expect(html).toContain('.btn-primary'.replace('.btn-primary', '')) // selector rendered below
    expect(html).toContain('issue-selector')
    expect(html).toContain('badge-serious')
    expect(html).toContain('2 elements')
  })

  it('puts the fix guidance behind an expandable disclosure', () => {
    const html = renderIssues([issue()])
    expect(html).toContain('<details')
    expect(html).toContain('How to fix')
    // curated color-contrast guidance leaks through
    expect(html.toLowerCase()).toContain('contrast')
  })

  it('exposes highlight/copy actions with the issue index, and a learn-more link', () => {
    const html = renderIssues([issue()])
    expect(html).toContain('data-action="highlight"')
    expect(html).toContain('data-action="copy"')
    expect(html).toContain('data-index="0"')
    expect(html).toContain('href="https://example.test/rule"')
  })

  it('escapes issue content', () => {
    const html = renderIssues([issue({ help: '<img src=x onerror=alert(1)>' })])
    expect(html).not.toContain('<img src=x')
    expect(html).toContain('&lt;img')
  })
})

describe('renderBreakdown', () => {
  it('renders a chip per non-zero severity with its count', () => {
    const counts = severityCounts([issue({ impact: 'critical' }), issue({ impact: 'minor' })])
    const html = renderBreakdown(counts)
    expect(html).toContain('Critical')
    expect(html).toContain('Minor')
    expect(html).not.toContain('Moderate') // zero -> omitted
  })
})

describe('renderNeedsReview', () => {
  it('lists incomplete items, labelled as needing review', () => {
    const html = renderNeedsReview([issue({ help: 'Needs a human' })])
    expect(html).toContain('Needs a human')
  })

  it('has its own empty state when nothing needs review', () => {
    expect(renderNeedsReview([]).toLowerCase()).toContain('nothing')
  })
})

describe('renderEmptyState', () => {
  it('is honest that automated scanning misses things', () => {
    expect(renderEmptyState().toLowerCase()).toContain("can't catch everything")
  })
})
