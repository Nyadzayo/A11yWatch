import { describe, expect, it } from 'vitest'

import { fakeStorage } from '../test/fakes'
import { clearSession, getSession, saveSession } from './session'

const SESSION = { baseUrl: 'http://api.test', token: 'tok', email: 'a@b.com' }

describe('session storage', () => {
  it('returns null when no session is stored', async () => {
    expect(await getSession(fakeStorage())).toBeNull()
  })

  it('round-trips a saved session', async () => {
    const storage = fakeStorage()
    await saveSession(SESSION, storage)
    expect(await getSession(storage)).toEqual(SESSION)
  })

  it('clears the session', async () => {
    const storage = fakeStorage()
    await saveSession(SESSION, storage)
    await clearSession(storage)
    expect(await getSession(storage)).toBeNull()
  })
})
