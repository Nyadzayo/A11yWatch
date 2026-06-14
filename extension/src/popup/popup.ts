import type { Message, MessageResponse } from '../background/messages'
import { DEFAULT_BASE_URL } from '../lib/config'
import type { ImpactGroup } from '../lib/audit'
import type { Scan } from '../lib/types'
import { renderGroupsHtml, summaryLine } from './render'

const POLL_INTERVAL_MS = 1500
const POLL_MAX_TRIES = 60 // ~90s ceiling against the per-site timeout

function send<T = unknown>(message: Message): Promise<MessageResponse<T>> {
  return chrome.runtime.sendMessage(message)
}

function el<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T
}

function showView(view: 'login' | 'audit'): void {
  el('login-view').hidden = view !== 'login'
  el('audit-view').hidden = view !== 'audit'
  el<HTMLButtonElement>('logout').hidden = view !== 'audit'
}

function enterAudit(email: string): void {
  el('who').textContent = email
  // Start clean for the signed-in account — never show the previous account's results.
  el('results').innerHTML = ''
  el('summary').textContent = ''
  el('status').textContent = ''
  showView('audit')
}

async function init(): Promise<void> {
  el<HTMLInputElement>('baseUrl').value = DEFAULT_BASE_URL
  try {
    const res = await send<{ email: string; baseUrl: string } | null>({ type: 'GET_SESSION' })
    if (res.ok && res.data) enterAudit(res.data.email)
    else showView('login')
  } catch {
    // Service worker cold-start / context invalidation: always fall back to a usable view.
    showView('login')
  }
}

el('login-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  el('login-error').textContent = ''
  const email = el<HTMLInputElement>('email').value.trim()
  const password = el<HTMLInputElement>('password').value
  const baseUrl = el<HTMLInputElement>('baseUrl').value.trim() || DEFAULT_BASE_URL
  const register = el<HTMLInputElement>('register').checked
  const res = await send<{ email: string }>({ type: 'LOGIN', email, password, baseUrl, register })
  if (res.ok) enterAudit(res.data.email)
  else el('login-error').textContent = res.error.message
})

el('logout').addEventListener('click', async () => {
  await send({ type: 'LOGOUT' })
  showView('login')
})

el('audit').addEventListener('click', async () => {
  const status = el('status')
  const button = el<HTMLButtonElement>('audit')
  el('results').innerHTML = ''
  el('summary').textContent = ''
  status.textContent = 'Starting scan…'
  button.disabled = true
  try {
    const started = await send<{ scanId: string; projectId: string }>({ type: 'AUDIT_CURRENT_TAB' })
    if (!started.ok) {
      status.textContent = started.error.message
      return
    }
    await pollAndRender(started.data.scanId, status)
  } finally {
    button.disabled = false
  }
})

async function pollAndRender(scanId: string, status: HTMLElement): Promise<void> {
  for (let i = 0; i < POLL_MAX_TRIES; i++) {
    const res = await send<Scan>({ type: 'GET_SCAN', scanId })
    if (!res.ok) {
      status.textContent = res.error.message
      return
    }
    const scan = res.data
    if (scan.status === 'succeeded') {
      status.textContent = ''
      el('summary').textContent = summaryLine(scan.total_issues, scan.new_issues, scan.resolved_issues)
      const violations = await send<{ total: number; groups: ImpactGroup[] }>({
        type: 'GET_VIOLATIONS',
        scanId,
      })
      if (violations.ok) el('results').innerHTML = renderGroupsHtml(violations.data.groups)
      else status.textContent = violations.error.message
      return
    }
    if (scan.status === 'failed') {
      status.textContent = 'Scan failed — please try again.'
      return
    }
    status.textContent = `Scanning… (${scan.status})`
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
  status.textContent = 'Scan is taking longer than expected. Check back shortly.'
}

void init()
