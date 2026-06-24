import type { Impact, Issue } from './types'

export const IMPACT_ORDER: readonly Impact[] = ['critical', 'serious', 'moderate', 'minor']

export interface ImpactGroup {
  impact: string
  issues: Issue[]
}

/** Group issues by impact, severest first; any unranked impact (incl. null) trails, stably. */
export function groupByImpact(issues: Issue[]): ImpactGroup[] {
  const buckets = new Map<string, Issue[]>()
  for (const issue of issues) {
    const key = issue.impact ?? 'unknown'
    const bucket = buckets.get(key)
    if (bucket) bucket.push(issue)
    else buckets.set(key, [issue])
  }
  const ordered: ImpactGroup[] = []
  for (const impact of IMPACT_ORDER) {
    const bucket = buckets.get(impact)
    if (bucket) {
      ordered.push({ impact, issues: bucket })
      buckets.delete(impact)
    }
  }
  for (const [impact, issues] of buckets) ordered.push({ impact, issues })
  return ordered
}

/** Flatten issues into a single severest-first list (the canonical UI order). */
export function sortBySeverity(issues: Issue[]): Issue[] {
  return groupByImpact(issues).flatMap((g) => g.issues)
}

export interface SeverityCounts {
  critical: number
  serious: number
  moderate: number
  minor: number
  unknown: number
  total: number
}

/** Count issues per severity (plus a grand total) for the headline breakdown. */
export function severityCounts(issues: Issue[]): SeverityCounts {
  const counts: SeverityCounts = {
    critical: 0,
    serious: 0,
    moderate: 0,
    minor: 0,
    unknown: 0,
    total: issues.length,
  }
  for (const issue of issues) {
    const key = (issue.impact ?? 'unknown') as keyof SeverityCounts
    counts[key]++
  }
  return counts
}
