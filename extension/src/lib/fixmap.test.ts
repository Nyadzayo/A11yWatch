import { describe, expect, it } from 'vitest'
import { fixForNode, fixGuidance } from './fixmap'
import type { Issue, IssueNode } from './types'

function issue(over: Partial<Issue> = {}): Issue {
  return {
    ruleId: 'color-contrast',
    impact: 'serious',
    help: 'Elements must meet color contrast minimums',
    description: 'Ensures the contrast between foreground and background colors meets WCAG',
    helpUrl: 'https://example.test',
    tags: ['wcag2aa', 'wcag143'],
    nodes: [],
    ...over,
  }
}

function node(over: Partial<IssueNode> = {}): IssueNode {
  return { target: '.btn', html: '<button>', failureSummary: null, ...over }
}

describe('fixGuidance', () => {
  it('returns curated guidance for common rules', () => {
    for (const rule of ['color-contrast', 'image-alt', 'label', 'link-name', 'heading-order']) {
      expect(fixGuidance(rule)).toBeTruthy()
    }
  })

  it('mentions the actual remedy (not a generic stub)', () => {
    expect(fixGuidance('color-contrast')?.toLowerCase()).toContain('contrast')
    expect(fixGuidance('image-alt')?.toLowerCase()).toContain('alt')
  })

  it('returns null for a rule with no curated entry', () => {
    expect(fixGuidance('some-obscure-rule')).toBeNull()
  })
})

describe('fixForNode', () => {
  it('prefers curated guidance when the rule is known', () => {
    const text = fixForNode(issue(), node({ failureSummary: 'axe summary here' }))
    expect(text).toBe(fixGuidance('color-contrast'))
  })

  it('falls back to the element failureSummary when no curated entry', () => {
    const text = fixForNode(
      issue({ ruleId: 'obscure', help: 'h', description: 'd' }),
      node({ failureSummary: 'Fix any of the following: do X' }),
    )
    expect(text).toBe('Fix any of the following: do X')
  })

  it('falls back to the rule description when there is neither', () => {
    const text = fixForNode(
      issue({ ruleId: 'obscure', description: 'The rule description' }),
      node({ failureSummary: null }),
    )
    expect(text).toBe('The rule description')
  })
})
