import type { ApiClient } from './api'
import type { Project, Violation } from './types'

/** Reuse a project already registered for this exact URL, else create one for the page. */
export async function findOrCreateProject(api: ApiClient, url: string): Promise<Project> {
  // Exact-match server-side query — O(1) reuse regardless of how many projects exist.
  const page = await api.listProjects(url)
  const existing = page.items.find((p) => p.base_url === url)
  if (existing) return existing
  return api.createProject({
    name: hostnameOf(url),
    base_url: url,
    url_list: [url],
    max_pages: 1,
  })
}

export async function auditUrl(
  api: ApiClient,
  url: string,
): Promise<{ scanId: string; projectId: string }> {
  const project = await findOrCreateProject(api, url)
  const scan = await api.triggerScan(project.id)
  return { scanId: scan.scan_id, projectId: project.id }
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname || url
  } catch {
    return url
  }
}

export const IMPACT_ORDER = ['critical', 'serious', 'moderate', 'minor'] as const

export interface ImpactGroup {
  impact: string
  violations: Violation[]
}

/** Group issues by impact, severest first; any unranked impact (incl. null) trails, stably. */
export function groupByImpact(violations: Violation[]): ImpactGroup[] {
  const buckets = new Map<string, Violation[]>()
  for (const v of violations) {
    const key = v.impact ?? 'unknown'
    const bucket = buckets.get(key)
    if (bucket) bucket.push(v)
    else buckets.set(key, [v])
  }
  const ordered: ImpactGroup[] = []
  for (const impact of IMPACT_ORDER) {
    const bucket = buckets.get(impact)
    if (bucket) {
      ordered.push({ impact, violations: bucket })
      buckets.delete(impact)
    }
  }
  for (const [impact, vs] of buckets) ordered.push({ impact, violations: vs })
  return ordered
}
