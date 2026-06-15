import { dispatch, type DispatchDeps } from './dispatch'
import type { Message } from './messages'

// chrome.storage.local is the source of truth; the worker holds no in-memory state.
const deps: DispatchDeps = {
  getActiveTabUrl: async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.url) throw new Error('No active tab URL')
    return tab.url
  },
}

// Register the listener at the top level — MV3 service workers are not persistent.
chrome.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
  dispatch(message, deps).then(sendResponse)
  return true // keep the message channel open for the async response
})
