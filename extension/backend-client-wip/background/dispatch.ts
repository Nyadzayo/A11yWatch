import { ApiClient, ApiError } from '../lib/api'
import { auditUrl, groupByImpact } from '../lib/audit'
import { clearSession, getSession, saveSession, type StorageArea } from '../lib/session'
import type { Message, MessageResponse } from './messages'

export interface DispatchDeps {
  getActiveTabUrl: () => Promise<string>
  storage?: StorageArea
  makeClient?: (baseUrl: string, token?: string | null) => ApiClient
}

function client(deps: DispatchDeps, baseUrl: string, token?: string | null): ApiClient {
  return deps.makeClient ? deps.makeClient(baseUrl, token) : new ApiClient({ baseUrl, token })
}

/** Route one popup message to the backend; all network lives here. Never throws. */
export async function dispatch(message: Message, deps: DispatchDeps): Promise<MessageResponse> {
  try {
    return { ok: true, data: await handle(message, deps) }
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: { code: e.code, message: e.message } }
    const message = e instanceof Error ? e.message : String(e)
    return { ok: false, error: { code: 'extension_error', message } }
  }
}

async function handle(message: Message, deps: DispatchDeps): Promise<unknown> {
  switch (message.type) {
    case 'LOGIN': {
      const api = client(deps, message.baseUrl)
      if (message.register) await api.register(message.email, message.password)
      const { access_token } = await api.login(message.email, message.password)
      const authed = client(deps, message.baseUrl, access_token)
      const me = await authed.me()
      await saveSession(
        { baseUrl: message.baseUrl, token: access_token, email: me.email },
        deps.storage,
      )
      return { email: me.email }
    }
    case 'LOGOUT':
      await clearSession(deps.storage)
      return { ok: true }
    case 'GET_SESSION': {
      const session = await getSession(deps.storage)
      return session ? { email: session.email, baseUrl: session.baseUrl } : null
    }
    case 'AUDIT_CURRENT_TAB': {
      const api = await authedClient(deps)
      const url = await deps.getActiveTabUrl()
      return auditUrl(api, url)
    }
    case 'GET_SCAN': {
      const api = await authedClient(deps)
      return api.getScan(message.scanId)
    }
    case 'GET_VIOLATIONS': {
      const api = await authedClient(deps)
      const page = await api.listViolations(message.scanId)
      return { total: page.total, groups: groupByImpact(page.items) }
    }
    default: {
      // Exhaustiveness guard + runtime safety: onMessage is an untyped global channel.
      const unknown = message as { type?: string }
      throw new ApiError(400, 'unknown_message', `Unknown message type: ${unknown.type}`)
    }
  }
}

async function authedClient(deps: DispatchDeps): Promise<ApiClient> {
  const session = await getSession(deps.storage)
  if (!session) throw new ApiError(401, 'unauthorized', 'Not signed in')
  return client(deps, session.baseUrl, session.token)
}
