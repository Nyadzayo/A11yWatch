import { describe, expect, it } from 'vitest'
import { filterByLevel, standardLabel, wcagLevel } from './wcag'
import type { Issue } from './types'

function issue(tags: string[], ruleId = 'r'): Issue {
  return { ruleId, impact: 'serious', help: '', description: '', helpUrl: '', tags, nodes: [] }
}

describe('wcagLevel', () => {
  it('reads the conformance level out of an axe wcag tag', () => {
    expect(wcagLevel(['cat.text-alternatives', 'wcag2a', 'wcag111'])).toBe('A')
    expect(wcagLevel(['wcag2aa', 'wcag143'])).toBe('AA')
    expect(wcagLevel(['wcag21aaa'])).toBe('AAA')
    expect(wcagLevel(['wcag22aa'])).toBe('AA')
  })

  it('returns null for best-practice / non-WCAG rules', () => {
    expect(wcagLevel(['best-practice', 'cat.semantics'])).toBeNull()
    expect(wcagLevel(['wcag143'])).toBeNull() // success-criterion number, not a level
  })
})

describe('filterByLevel', () => {
  const a = issue(['wcag2a'], 'a')
  const aa = issue(['wcag2aa'], 'aa')
  const aaa = issue(['wcag21aaa'], 'aaa')
  const bp = issue(['best-practice'], 'bp')

  it('AA keeps A and AA but not AAA', () => {
    const kept = filterByLevel([a, aa, aaa], 'AA').map((i) => i.ruleId)
    expect(kept).toEqual(['a', 'aa'])
  })

  it('A keeps only level-A rules', () => {
    expect(filterByLevel([a, aa, aaa], 'A').map((i) => i.ruleId)).toEqual(['a'])
  })

  it('AAA keeps everything that has a level', () => {
    expect(filterByLevel([a, aa, aaa], 'AAA').map((i) => i.ruleId)).toEqual(['a', 'aa', 'aaa'])
  })

  it('always keeps best-practice rules (they have no level to exclude on)', () => {
    expect(filterByLevel([a, bp], 'A').map((i) => i.ruleId)).toEqual(['a', 'bp'])
  })
})

describe('standardLabel', () => {
  it('names the active standard', () => {
    expect(standardLabel('AA')).toBe('WCAG 2.1 AA')
    expect(standardLabel('A')).toBe('WCAG 2.1 A')
  })
})
