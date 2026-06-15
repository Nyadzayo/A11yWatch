import { describe, expect, it } from 'vitest'
import { GRADE_BANDS, scoreFor, SEVERITY_WEIGHTS } from './score'
import type { Issue } from './types'

function issue(impact: Issue['impact']): Issue {
  return { ruleId: 'r', impact, help: '', description: '', helpUrl: '', tags: [], nodes: [] }
}

describe('scoreFor', () => {
  it('is a perfect 100 / A with no issues', () => {
    expect(scoreFor([])).toEqual({ value: 100, grade: 'A' })
  })

  it('deducts the configured weight per issue, severity-weighted', () => {
    // one critical = -10 by default weights
    expect(scoreFor([issue('critical')]).value).toBe(100 - SEVERITY_WEIGHTS.critical)
    // mixed bag deducts the sum
    const value = scoreFor([issue('critical'), issue('serious'), issue('minor')]).value
    const expected =
      100 - SEVERITY_WEIGHTS.critical - SEVERITY_WEIGHTS.serious - SEVERITY_WEIGHTS.minor
    expect(value).toBe(expected)
  })

  it('weights an unknown impact like a minor', () => {
    expect(scoreFor([issue(null)]).value).toBe(100 - SEVERITY_WEIGHTS.minor)
  })

  it('floors at 0 and never goes negative', () => {
    const many = Array.from({ length: 50 }, () => issue('critical'))
    expect(scoreFor(many).value).toBe(0)
    expect(scoreFor(many).grade).toBe('F')
  })

  it('assigns letter grades on the published bands', () => {
    // value 100 -> A, 60 -> D (lower bound), 59 -> F
    expect(scoreFor([]).grade).toBe('A')
    expect(GRADE_BANDS.A).toBe(90)
    expect(GRADE_BANDS.F).toBe(0)
  })
})
