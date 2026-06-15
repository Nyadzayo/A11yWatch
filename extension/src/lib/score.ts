import type { Issue } from './types'

/** Penalty points deducted per issue, by severity. An unknown impact is treated as minor.
 *  Tunable in one place; the score is a heuristic, not a conformance verdict. */
export const SEVERITY_WEIGHTS = {
  critical: 10,
  serious: 5,
  moderate: 2,
  minor: 1,
} as const

/** Lower bound (inclusive) of each letter grade on the 0–100 scale. */
export const GRADE_BANDS = {
  A: 90,
  B: 80,
  C: 70,
  D: 60,
  F: 0,
} as const

export type Grade = keyof typeof GRADE_BANDS

export interface Score {
  value: number
  grade: Grade
}

function weightOf(impact: Issue['impact']): number {
  if (impact && impact in SEVERITY_WEIGHTS) {
    return SEVERITY_WEIGHTS[impact as keyof typeof SEVERITY_WEIGHTS]
  }
  return SEVERITY_WEIGHTS.minor
}

function gradeFor(value: number): Grade {
  if (value >= GRADE_BANDS.A) return 'A'
  if (value >= GRADE_BANDS.B) return 'B'
  if (value >= GRADE_BANDS.C) return 'C'
  if (value >= GRADE_BANDS.D) return 'D'
  return 'F'
}

/** Severity-weighted page score: 100 minus the summed per-issue penalty, floored at 0. */
export function scoreFor(issues: Issue[]): Score {
  const penalty = issues.reduce((sum, issue) => sum + weightOf(issue.impact), 0)
  const value = Math.max(0, 100 - penalty)
  return { value, grade: gradeFor(value) }
}
