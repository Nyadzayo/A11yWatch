// Generates the extension/store icons (16/32/48/128) with no external dependencies:
// renders a teal rounded-square "eye" mark at high resolution and area-downsamples it
// (premultiplied alpha) for clean edges, then encodes PNGs by hand via node:zlib.
import { mkdirSync, writeFileSync } from 'node:fs'
import { deflateSync } from 'node:zlib'

const MASTER = 768 // divisible by 16/32/48/128 for integer downsampling
// Marketing palette: ink square, peach eye ring, rust pupil (matches docs/assets/favicon.svg).
const INK = [26, 23, 20] // #1A1714
const PEACH = [232, 167, 143] // #E8A78F
const RUST = [178, 58, 30] // #B23A1E

// Signed distance to a full-bleed rounded square; <= 0 is inside.
function sdfRoundRect(x, y, size, r) {
  const half = size / 2
  const px = Math.abs(x - half) - (half - r)
  const py = Math.abs(y - half) - (half - r)
  const dx = Math.max(px, 0)
  const dy = Math.max(py, 0)
  return Math.hypot(dx, dy) + Math.min(Math.max(px, py), 0) - r
}

function renderMaster() {
  const s = MASTER
  const buf = new Float64Array(s * s * 4) // premultiplied rgba, 0..255
  const cx = s / 2
  const cy = s / 2
  const cornerR = s * 0.22 // ink rounded square
  const ringOuter = s * 0.3
  const ringInner = s * 0.2 // peach eye ring (annulus)
  const pupilR = s * 0.11 // rust pupil
  for (let y = 0; y < s; y++) {
    for (let x = 0; x < s; x++) {
      const i = (y * s + x) * 4
      if (sdfRoundRect(x + 0.5, y + 0.5, s, cornerR) > 0) continue // transparent corners
      const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy)
      let rgb = INK
      if (d <= ringOuter && d > ringInner) rgb = PEACH
      if (d <= pupilR) rgb = RUST
      buf[i] = rgb[0]
      buf[i + 1] = rgb[1]
      buf[i + 2] = rgb[2]
      buf[i + 3] = 255
    }
  }
  return buf
}

function downsample(master, target) {
  const f = MASTER / target
  const out = Buffer.alloc(target * target * 4)
  for (let y = 0; y < target; y++) {
    for (let x = 0; x < target; x++) {
      let r = 0
      let g = 0
      let b = 0
      let a = 0
      for (let sy = 0; sy < f; sy++) {
        for (let sx = 0; sx < f; sx++) {
          const mi = ((y * f + sy) * MASTER + (x * f + sx)) * 4
          const ma = master[mi + 3]
          r += master[mi] * (ma / 255)
          g += master[mi + 1] * (ma / 255)
          b += master[mi + 2] * (ma / 255)
          a += ma
        }
      }
      const n = f * f
      const avgA = a / n
      const oi = (y * target + x) * 4
      // un-premultiply
      const scale = avgA > 0 ? 255 / avgA : 0
      out[oi] = Math.round((r / n) * scale)
      out[oi + 1] = Math.round((g / n) * scale)
      out[oi + 2] = Math.round((b / n) * scale)
      out[oi + 3] = Math.round(avgA)
    }
  }
  return out
}

// --- minimal PNG encoder (RGBA, 8-bit) ---
const CRC_TABLE = (() => {
  const t = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c >>> 0
  }
  return t
})()
function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}
function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length, 0)
  const typeBuf = Buffer.from(type, 'ascii')
  const body = Buffer.concat([typeBuf, data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body), 0)
  return Buffer.concat([len, body, crc])
}
function encodePng(rgba, size) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // color type RGBA
  // 10,11,12 = compression/filter/interlace = 0
  const raw = Buffer.alloc(size * (size * 4 + 1))
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0 // filter: none
    rgba.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4)
  }
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

mkdirSync('icons', { recursive: true })
const master = renderMaster()
for (const size of [16, 32, 48, 128]) {
  const png = encodePng(downsample(master, size), size)
  writeFileSync(`icons/icon${size}.png`, png)
  console.log(`make-icons: icons/icon${size}.png (${png.length} bytes)`)
}
