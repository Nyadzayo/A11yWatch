import { describe, expect, it, vi } from 'vitest'

import { auditUrl, findOrCreateProject, groupByImpact } from './audit'

function fakeApi(over: Record<string, unknown> = {}): any {
  return {
    listProjects: vi.fn(async () => ({ items: [], total: 0, limit: 100, offset: 0 })),
    createProject: vi.fn(async (p: any) => ({
      id: 'new',
      name: p.name,
      base_url: p.base_url,
      status: 'idle',
    })),
    triggerScan: vi.fn(async () => ({ scan_id: 's1', job_id: 'j1', status: 'queued' })),
    ...over,
  }
}

describe('findOrCreateProject', () => {
  it('reuses an existing project with the same base_url', async () => {
    const api = fakeApi({
      listProjects: vi.fn(async () => ({
        items: [{ id: 'e', name: 'n', base_url: 'http://x/p', status: 'idle' }],
        total: 1,
        limit: 100,
        offset: 0,
      })),
    })
    const p = await findOrCreateProject(api, 'http://x/p')
    expect(p.id).toBe('e')
    expect(api.createProject).not.toHaveBeenCalled()
  })

  it('queries projects by the exact url (server-side filter) before creating', async () => {
    const api = fakeApi()
    await findOrCreateProject(api, 'https://site.test/page')
    expect(api.listProjects).toHaveBeenCalledWith('https://site.test/page')
  })

  it('creates a project keyed on the exact url when none matches', async () => {
    const api = fakeApi()
    const p = await findOrCreateProject(api, 'https://site.test/page')
    expect(api.createProject).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'site.test',
        base_url: 'https://site.test/page',
        url_list: ['https://site.test/page'],
        max_pages: 1,
      }),
    )
    expect(p.id).toBe('new')
  })
})

describe('auditUrl', () => {
  it('finds/creates a project then triggers a scan', async () => {
    const api = fakeApi()
    const r = await auditUrl(api, 'https://site.test/page')
    expect(r.scanId).toBe('s1')
    expect(r.projectId).toBe('new')
    expect(api.triggerScan).toHaveBeenCalledWith('new')
  })
})

describe('groupByImpact', () => {
  it('orders critical→serious→moderate→minor and buckets unknown last', () => {
    const v = (impact: string | null) => ({ rule_id: 'r', impact }) as any
    const groups = groupByImpact([v('minor'), v('critical'), v(null), v('serious')])
    expect(groups.map((g) => g.impact)).toEqual(['critical', 'serious', 'minor', 'unknown'])
    expect(groups[0].violations).toHaveLength(1)
  })
})
