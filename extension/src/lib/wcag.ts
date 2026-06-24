import type { Issue } from './types'

export type WcagLevel = 'A' | 'AA' | 'AAA'

/** The WCAG version we run axe against (tags below are limited to 2.0/2.1 rules). */
export const WCAG_VERSION = '2.1'

/** axe tags that select the rules we run — WCAG 2.0/2.1 A & AA, plus best-practice. */
export const ACTIVE_AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']

const LEVEL_RANK: Record<WcagLevel, number> = { A: 1, AA: 2, AAA: 3 }
// e.g. wcag2a -> A, wcag2aa -> AA, wcag21aaa -> AAA. The numeric part is the version,
// the trailing a's are the conformance level. `wcag111` (a success criterion) does NOT match.
const LEVEL_TAG = /^wcag\d+(a{1,3})$/

/** The conformance level a rule belongs to, from its axe tags, or null (best-practice). */
export function wcagLevel(tags: string[]): WcagLevel | null {
  for (const tag of tags) {
    const m = LEVEL_TAG.exec(tag)
    if (m) return (['A', 'AA', 'AAA'] as const)[m[1].length - 1]
  }
  return null
}

/** Keep issues at or below `maxLevel`. Best-practice rules (no level) are always kept. */
export function filterByLevel(issues: Issue[], maxLevel: WcagLevel): Issue[] {
  const ceiling = LEVEL_RANK[maxLevel]
  return issues.filter((issue) => {
    const level = wcagLevel(issue.tags)
    return level === null || LEVEL_RANK[level] <= ceiling
  })
}

/** Human label for the active standard, e.g. "WCAG 2.1 AA". */
export function standardLabel(level: WcagLevel): string {
  return `WCAG ${WCAG_VERSION} ${level}`
}
