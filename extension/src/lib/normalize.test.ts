import { describe, expect, it } from 'vitest'
import { normalizeAxeResults } from './normalize'
import type { AxeResults } from './types'

function rule(over: Partial<AxeResults['violations'][number]> = {}) {
  return {
    id: 'image-alt',
    impact: 'critical' as const,
    tags: ['wcag2a', 'wcag111'],
    description: 'Ensures img elements have alternate text',
    help: 'Images must have alternate text',
    helpUrl: 'https://dequeuniversity.com/rules/axe/4.12/image-alt',
    nodes: [
      { target: ['img.hero'], html: '<img class="hero">', failureSummary: 'Fix this: add alt' },
    ],
    ...over,
  }
}

function results(over: Partial<AxeResults> = {}): AxeResults {
  return { violations: [], incomplete: [], passes: [], inapplicable: [], ...over }
}

describe('normalizeAxeResults', () => {
  it('maps violations to issues, carrying rule + node detail', () => {
    const scan = normalizeAxeResults(results({ violations: [rule()] }), 'https://acme.test')
    expect(scan.url).toBe('https://acme.test')
    expect(scan.issues).toHaveLength(1)
    const issue = scan.issues[0]
    expect(issue.ruleId).toBe('image-alt')
    expect(issue.impact).toBe('critical')
    expect(issue.help).toBe('Images must have alternate text')
    expect(issue.nodes).toHaveLength(1)
    expect(issue.nodes[0].target).toBe('img.hero')
    expect(issue.nodes[0].failureSummary).toBe('Fix this: add alt')
  })

  it('joins multi-part (shadow DOM) targets into one selector string', () => {
    const r = rule({ nodes: [{ target: [['#host', '.inner'], 'button'], html: '<button>' }] })
    const scan = normalizeAxeResults(results({ violations: [r] }), 'x')
    expect(scan.issues[0].nodes[0].target).toBe('#host .inner button')
  })

  it('coalesces a missing failureSummary to null', () => {
    const r = rule({ nodes: [{ target: ['a'], html: '<a>' }] })
    const scan = normalizeAxeResults(results({ violations: [r] }), 'x')
    expect(scan.issues[0].nodes[0].failureSummary).toBeNull()
  })

  it('routes incomplete results to needsReview and NEVER into issues', () => {
    const scan = normalizeAxeResults(
      results({ violations: [rule()], incomplete: [rule({ id: 'color-contrast' })] }),
      'x',
    )
    expect(scan.issues.map((i) => i.ruleId)).toEqual(['image-alt'])
    expect(scan.needsReview.map((i) => i.ruleId)).toEqual(['color-contrast'])
  })

  it('counts passes and inapplicable rules', () => {
    const scan = normalizeAxeResults(
      results({ passes: [rule(), rule()], inapplicable: [rule()] }),
      'x',
    )
    expect(scan.passCount).toBe(2)
    expect(scan.inapplicableCount).toBe(1)
  })
})
