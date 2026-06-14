import type { Page, Project, ProjectCreate, Scan, Violation } from './types'

/** A backend error surfaced from the `{ error: { code, message } }` envelope. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export interface ApiClientOptions {
  baseUrl: string
  token?: string | null
  fetch?: typeof fetch
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string }
}

export class ApiClient {
  private readonly baseUrl: string
  private readonly token: string | null
  private readonly fetchImpl: typeof fetch

  constructor(opts: ApiClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, '')
    this.token = opts.token ?? null
    // Native fetch must be called with `this` === the global scope, or a service worker
    // raises "Illegal invocation". Bind it; an injected fetch (tests) is used as-is.
    this.fetchImpl = opts.fetch ?? globalThis.fetch.bind(globalThis)
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (res.status === 204) return undefined as T
    let data: unknown
    try {
      data = await res.json()
    } catch {
      data = undefined
    }
    if (!res.ok) {
      const err = (data as ErrorEnvelope | undefined)?.error
      const message = err?.message || res.statusText || `HTTP ${res.status}`
      throw new ApiError(res.status, err?.code ?? 'error', message)
    }
    if (data === undefined) {
      throw new ApiError(res.status, 'invalid_response', 'Malformed response body')
    }
    return data as T
  }

  login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    return this.request('POST', '/api/v1/auth/login', { email, password })
  }

  register(email: string, password: string): Promise<{ id: string; email: string }> {
    return this.request('POST', '/api/v1/auth/register', { email, password })
  }

  me(): Promise<{ id: string; email: string }> {
    return this.request('GET', '/api/v1/auth/me')
  }

  listProjects(baseUrl?: string): Promise<Page<Project>> {
    const query = baseUrl
      ? `?base_url=${encodeURIComponent(baseUrl)}&limit=100`
      : '?limit=100'
    return this.request('GET', `/api/v1/projects${query}`)
  }

  createProject(payload: ProjectCreate): Promise<Project> {
    return this.request('POST', '/api/v1/projects', payload)
  }

  triggerScan(projectId: string): Promise<{ scan_id: string; job_id: string; status: string }> {
    return this.request('POST', `/api/v1/projects/${projectId}/scans`)
  }

  getScan(scanId: string): Promise<Scan> {
    return this.request('GET', `/api/v1/scans/${scanId}`)
  }

  listViolations(scanId: string): Promise<Page<Violation>> {
    return this.request('GET', `/api/v1/scans/${scanId}/violations?limit=100`)
  }
}
