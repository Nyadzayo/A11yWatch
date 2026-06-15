import { defineConfig } from 'vite'
import { crx } from '@crxjs/vite-plugin'
import manifest from './manifest.json' with { type: 'json' }

export default defineConfig({
  plugins: [crx({ manifest })],
  build: {
    // The popup is a single chunk — drop Vite's modulepreload polyfill so the bundle makes
    // zero fetch() calls (keeps the package provably network-free for store review).
    modulePreload: false,
  },
})
