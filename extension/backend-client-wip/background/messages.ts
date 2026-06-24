export type Message =
  | { type: 'LOGIN'; email: string; password: string; baseUrl: string; register?: boolean }
  | { type: 'LOGOUT' }
  | { type: 'GET_SESSION' }
  | { type: 'AUDIT_CURRENT_TAB' }
  | { type: 'GET_SCAN'; scanId: string }
  | { type: 'GET_VIOLATIONS'; scanId: string }

export type MessageResponse<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } }
