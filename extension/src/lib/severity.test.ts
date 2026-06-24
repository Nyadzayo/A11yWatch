import { describe, expect, it } from 'vitest'
import { groupByImpact, IMPACT_ORDER, severityCounts, sortBySeverity } from './severity'
import type { Issue } from './types'

function issue(impact: Issue['impact'], ruleId = 'r'): Issue {
  return { ruleId, impact, help: '', description: '', helpUrl: '', tags: [], nodes: [] }
}

describe('IMPACT_ORDER', () => {
  it('runs severest-first', () => {
    expect(IMPACT_ORDER).toEqual(['critical', 'serious', 'moderate', 'minor'])
  })
})

describe('groupByImpact', () => {
  it('orders groups severest-first regardless of input order', () => {
    const groups = groupByImpact([issue('minor'), issue('critical'), issue('moderate')])
    expect(groups.map((g) => g.impact)).toEqual(['critical', 'moderate', 'minor'])
  })

  it('trails unranked/null impacts after the known severities', () => {
    const groups = groupByImpact([issue(null, 'x'), issue('serious')])
    expect(groups.map((g) => g.impact)).toEqual(['serious', 'unknown'])
  })

  it('keeps every issue in its bucket', () => {
    const groups = groupByImpact([issue('critical', 'a'), issue('critical', 'b')])
    expect(groups[0].issues.map((i) => i.ruleId)).toEqual(['a', 'b'])
  })
})

describe('sortBySeverity', () => {
  it('returns a flat list, severest-first, unranked last', () => {
    const sorted = sortBySeverity([
      issue('minor', 'm'),
      issue(null, 'u'),
      issue('critical', 'c'),
      issue('moderate', 'mo'),
    ])
    expect(sorted.map((i) => i.ruleId)).toEqual(['c', 'mo', 'm', 'u'])
  })
})

describe('severityCounts', () => {
  it('counts issues per severity plus a total', () => {
    const counts = severityCounts([
      issue('critical'),
      issue('critical'),
      issue('serious'),
      issue('minor'),
      issue(null),
    ])
    expect(counts).toEqual({
      critical: 2,
      serious: 1,
      moderate: 0,
      minor: 1,
      unknown: 1,
      total: 5,
    })
  })
})
