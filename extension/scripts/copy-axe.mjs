// Vendor axe-core into public/ so chrome.scripting can inject it as a packaged file.
// axe-core is BUNDLED locally and never fetched from a CDN at runtime (store policy).
// Runs automatically before `dev` and `build`; keeps public/axe.min.js pinned to the
// installed axe-core version.
import { copyFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const src = require.resolve('axe-core/axe.min.js')
const version = require('axe-core/package.json').version

mkdirSync('public', { recursive: true })
copyFileSync(src, 'public/axe.min.js')
console.log(`copy-axe: vendored axe-core ${version} -> public/axe.min.js`)
