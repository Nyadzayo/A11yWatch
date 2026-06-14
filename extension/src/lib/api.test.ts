import { describe, expect, it } from 'vitest'

import { ApiClient } from './api'

function client(handler: (url: string, init: any) => Response, token?: string) {
  const fetchImpl = (async (url: any, init: any) => handler(String(url), init)) as unknown as typeof fetch
  return new ApiClient({ baseUrl: 'http://api.test/', token, fetch: fetchImpl })
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status })
}

describe('ApiClient', () => {
  it('login posts credentials (no auth header) and returns the token', async () => {
    let captured: any
    const c = client((url, init) => {
      captured = { url, init }
      return json(200, { access_token: 't', token_type: 'bearer' })
    })
    const res = await c.login('a@b.com', 'secret123')
    expect(res.access_token).toBe('t')
    expect(captured.url).toBe('http://api.test/api/v1/auth/login')
    expect(captured.init.method).toBe('POST')
    expect(JSON.parse(captured.init.body)).toEqual({ email: 'a@b.com', password: 'secret123' })
    expect(captured.init.headers['Authorization']).toBeUndefined()
  })

  it('attaches a Bearer token on authenticated calls', async () => {
    let headers: any
    const c = client((_url, init) => {
      headers = init.headers
      return json(200, { id: '1', email: 'a@b.com' })
    }, 'tok')
    await c.me()
    expect(headers['Authorization']).toBe('Bearer tok')
  })

  it('throws ApiError carrying code+status from the error envelope', async () => {
    const c = client(() => json(422, { error: { code: 'validation_error', message: 'bad' } }))
    await expect(c.createProject({ name: 'x', base_url: 'https://y' })).rejects.toMatchObject({
      code: 'validation_error',
      status: 422,
      message: 'bad',
    })
  })

  it('builds the scan violations path', async () => {
    let url = ''
    const c = client((u) => {
      url = u
      return json(200, { items: [], total: 0, limit: 100, offset: 0 })
    }, 'tok')
    await c.listViolations('scan-1')
    expect(url).toContain('/api/v1/scans/scan-1/violations')
  })

  it('triggerScan POSTs to the project scans path', async () => {
    let captured: any
    const c = client((url, init) => {
      captured = { url, init }
      return json(202, { scan_id: 's1', job_id: 'j1', status: 'queued' })
    }, 'tok')
    const res = await c.triggerScan('proj-1')
    expect(captured.url).toBe('http://api.test/api/v1/projects/proj-1/scans')
    expect(captured.init.method).toBe('POST')
    expect(res.scan_id).toBe('s1')
  })

  it('listProjects with a base_url filters via an encoded query param', async () => {
    let url = ''
    const c = client((u) => {
      url = u
      return json(200, { items: [], total: 0, limit: 100, offset: 0 })
    }, 'tok')
    await c.listProjects('https://site.test/page')
    expect(url).toContain('base_url=https%3A%2F%2Fsite.test%2Fpage')
  })

  it('resolves to undefined on 204 without parsing a body', async () => {
    const c = client(() => new Response(null, { status: 204 }), 'tok')
    await expect(c.me()).resolves.toBeUndefined()
  })

  it('non-JSON error body still yields ApiError with a non-empty message', async () => {
    const c = client(() => new Response('<html>oops</html>', { status: 500, statusText: 'Server Error' }))
    await expect(c.me()).rejects.toMatchObject({ status: 500, code: 'error', message: 'Server Error' })
  })

  it('error envelope missing the error key falls back to a stable message', async () => {
    const c = client(() => json(422, { detail: 'nope' }))
    await expect(c.me()).rejects.toMatchObject({ status: 422, code: 'error' })
  })

  it('throws invalid_response on a malformed body for a successful response', async () => {
    const c = client(() => new Response('not json', { status: 200 }), 'tok')
    await expect(c.me()).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('invokes the global fetch with the correct this-binding when none is injected', async () => {
    // In a service worker the global fetch raises "Illegal invocation" unless called with
    // this === the global scope. Model that to lock in the binding.
    const orig = globalThis.fetch
    const seen: string[] = []
    function nativeLike(this: unknown, url: unknown) {
      if (this !== globalThis && this !== undefined) throw new TypeError('Illegal invocation')
      seen.push(String(url))
      return Promise.resolve(new Response(JSON.stringify({ id: '1', email: 'a@b.com' }), { status: 200 }))
    }
    ;(globalThis as any).fetch = nativeLike
    try {
      const c = new ApiClient({ baseUrl: 'http://api.test', token: 'tok' })
      await c.me()
      expect(seen).toEqual(['http://api.test/api/v1/auth/me'])
    } finally {
      ;(globalThis as any).fetch = orig
    }
  })
})
