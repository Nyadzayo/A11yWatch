import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../lib/api'
import { fakeStorage } from '../test/fakes'
import { dispatch } from './dispatch'

function setup(apiOver: Record<string, unknown> = {}, tabUrl = 'https://site.test/page') {
  const storage = fakeStorage()
  const api: any = {
    login: vi.fn(async () => ({ access_token: 'tok', token_type: 'bearer' })),
    register: vi.fn(async () => ({})),
    me: vi.fn(async () => ({ id: 'u1', email: 'a@b.com' })),
    listProjects: vi.fn(async () => ({ items: [], total: 0, limit: 100, offset: 0 })),
    createProject: vi.fn(async (p: any) => ({ id: 'p1', name: p.name, base_url: p.base_url, status: 'idle' })),
    triggerScan: vi.fn(async () => ({ scan_id: 's1', job_id: 'j1', status: 'queued' })),
    getScan: vi.fn(async () => ({ id: 's1', status: 'succeeded' })),
    listViolations: vi.fn(async () => ({ items: [], total: 0, limit: 100, offset: 0 })),
    ...apiOver,
  }
  const makeClient = vi.fn((_baseUrl: string, _token?: string | null) => api)
  const deps = { storage, getActiveTabUrl: async () => tabUrl, makeClient }
  return { storage, api, makeClient, deps }
}

async function seedSession(storage: any) {
  await storage.set({ session: { baseUrl: 'http://api.test', token: 'tok', email: 'a@b.com' } })
}

describe('dispatch', () => {
  it('LOGIN authenticates, builds the authed client with the new token, and persists the session', async () => {
    const { deps, storage, api, makeClient } = setup()
    const res = await dispatch(
      { type: 'LOGIN', email: 'a@b.com', password: 'secret123', baseUrl: 'http://api.test' },
      deps,
    )
    expect(res).toEqual({ ok: true, data: { email: 'a@b.com' } })
    expect(api.login).toHaveBeenCalled()
    // First an anonymous client (no token), then an authed client carrying the returned token.
    expect(makeClient).toHaveBeenNthCalledWith(1, 'http://api.test', undefined)
    expect(makeClient).toHaveBeenNthCalledWith(2, 'http://api.test', 'tok')
    const saved = (await storage.get('session')) as any
    expect(saved.session).toMatchObject({ token: 'tok', email: 'a@b.com', baseUrl: 'http://api.test' })
  })

  it('LOGIN with register=true registers BEFORE logging in', async () => {
    const { deps, api } = setup()
    await dispatch(
      { type: 'LOGIN', email: 'a@b.com', password: 'secret123', baseUrl: 'http://api.test', register: true },
      deps,
    )
    expect(api.register.mock.invocationCallOrder[0]).toBeLessThan(api.login.mock.invocationCallOrder[0])
  })

  it('AUDIT_CURRENT_TAB builds the client from the stored session (baseUrl + token)', async () => {
    const { deps, storage, api, makeClient } = setup()
    await seedSession(storage)
    const res = await dispatch({ type: 'AUDIT_CURRENT_TAB' }, deps)
    expect(res).toEqual({ ok: true, data: { scanId: 's1', projectId: 'p1' } })
    expect(makeClient).toHaveBeenCalledWith('http://api.test', 'tok')
    expect(api.triggerScan).toHaveBeenCalled()
  })

  it.each(['AUDIT_CURRENT_TAB', 'GET_SCAN', 'GET_VIOLATIONS'] as const)(
    '%s requires a session',
    async (type) => {
      const { deps } = setup()
      const res = await dispatch({ type, scanId: 's1' } as any, deps)
      expect(res).toEqual({ ok: false, error: { code: 'unauthorized', message: 'Not signed in' } })
    },
  )

  it('GET_SESSION returns only email + baseUrl, never the token', async () => {
    const { deps, storage } = setup()
    await seedSession(storage)
    const res = await dispatch({ type: 'GET_SESSION' }, deps)
    expect(res).toEqual({ ok: true, data: { email: 'a@b.com', baseUrl: 'http://api.test' } })
    expect((res as any).data.token).toBeUndefined()
  })

  it('maps ApiError to an error response envelope', async () => {
    const { deps, storage, api } = setup()
    api.triggerScan = vi.fn(async () => {
      throw new ApiError(409, 'conflict', 'already running')
    })
    await seedSession(storage)
    const res = await dispatch({ type: 'AUDIT_CURRENT_TAB' }, deps)
    expect(res).toEqual({ ok: false, error: { code: 'conflict', message: 'already running' } })
  })

  it('coerces a non-Error throw into a stable error message', async () => {
    const { deps, storage, api } = setup()
    api.triggerScan = vi.fn(async () => {
      throw 'boom-string'
    })
    await seedSession(storage)
    const res = await dispatch({ type: 'AUDIT_CURRENT_TAB' }, deps)
    expect(res).toEqual({ ok: false, error: { code: 'extension_error', message: 'boom-string' } })
  })

  it('LOGOUT clears the session', async () => {
    const { deps, storage } = setup()
    await seedSession(storage)
    const res = await dispatch({ type: 'LOGOUT' }, deps)
    expect(res.ok).toBe(true)
    expect((await storage.get('session')).session).toBeUndefined()
  })

  it('returns a structured error for an unknown message type', async () => {
    const { deps } = setup()
    const res = await dispatch({ type: 'NOPE' } as any, deps)
    expect(res).toEqual({ ok: false, error: { code: 'unknown_message', message: expect.any(String) } })
  })
})
