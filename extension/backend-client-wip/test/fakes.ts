import type { StorageArea } from '../lib/session'

/** In-memory StorageArea matching the chrome.storage.local promise API, for tests. */
export function fakeStorage(): StorageArea {
  const data: Record<string, unknown> = {}
  return {
    async get(keys) {
      if (keys === null || keys === undefined) return { ...data }
      const arr = Array.isArray(keys) ? keys : [keys]
      const out: Record<string, unknown> = {}
      for (const k of arr) if (k in data) out[k] = data[k]
      return out
    },
    async set(items) {
      Object.assign(data, items)
    },
    async remove(keys) {
      const arr = Array.isArray(keys) ? keys : [keys]
      for (const k of arr) delete data[k]
    },
  }
}
