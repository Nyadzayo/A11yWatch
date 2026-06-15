import type { Session } from './types'

/** The subset of chrome.storage.local (promise form) we depend on — injectable for tests. */
export interface StorageArea {
  get(keys: string | string[] | null): Promise<Record<string, unknown>>
  set(items: Record<string, unknown>): Promise<void>
  remove(keys: string | string[]): Promise<void>
}

const KEY = 'session'

function area(custom?: StorageArea): StorageArea {
  return custom ?? (chrome.storage.local as unknown as StorageArea)
}

export async function getSession(storage?: StorageArea): Promise<Session | null> {
  const data = await area(storage).get(KEY)
  return (data[KEY] as Session | undefined) ?? null
}

export async function saveSession(session: Session, storage?: StorageArea): Promise<void> {
  await area(storage).set({ [KEY]: session })
}

export async function clearSession(storage?: StorageArea): Promise<void> {
  await area(storage).remove(KEY)
}
