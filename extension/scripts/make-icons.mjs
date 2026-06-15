// Generates the extension/store icons (16/32/48/128) with no external dependencies:
// renders a teal rounded-square "eye" mark at high resolution and area-downsamples it
// (premultiplied alpha) for clean edges, then encodes PNGs by hand via node:zlib.
import { mkdirSync, writeFileSync } from 'node:fs'
import { deflateSync } from 'node:zlib'

const MASTER = 768 // divisible by 16/32/48/128 for integer downsampling
// Marketing palette (docs/assets/favicon.svg): ink square, cream sclera, rust iris, peach rim.
// Gradient endpoints give the eye depth (iris radial shade, sclera + eyelid shading, catchlight).
const PEACH = [232, 167, 143] // #E8A78F — almond rim
const WHITE = [255, 255, 255] // catchlight
const BG_TOP = [37, 30, 24] // #251E18 — ink square, lit from top
const BG_BOTTOM = [22, 19, 15] // #16130F
const SCLERA_TOP = [255, 253, 249] // #FFFDF9
const SCLERA_BOTTOM = [240, 230, 214] // #F0E6D6
const EYELID_SHADOW = [40, 28, 20] // warm shade under the upper lid
const IRIS_IN = [203, 82, 48] // #CB5230 — bright centre
const IRIS_OUT = [126, 41, 18] // #7E2912 — deep edge
const IRIS_RIM = [94, 31, 15] // #5E1F0F — limbal ring
const PUPIL = [21, 14, 9] // #150E09

const clamp01 = (t) => (t < 0 ? 0 : t > 1 ? 1 : t)
const smooth = (t) => {
  t = clamp01(t)
  return t * t * (3 - 2 * t)
}
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]

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
  const cornerR = s * 0.22 // ink rounded square (favicon rx)
  // Almond (vesica) eye: intersection of two equal circles offset vertically. Pick R and the
  // offset c from the desired half-width w and half-height h of the eye.
  const w = s * 0.34
  const h = s * 0.2
  const R = (w * w + h * h) / (2 * h)
  const c = R - h
  const ay = cy + c // lower circle centre
  const by = cy - c // upper circle centre
  const irisR = s * 0.135
  const pupilR = s * 0.062
  const rim = s * 0.018 // peach outline half-width
  const hiR = s * 0.032 // catchlight
  const hiX = cx - s * 0.06
  const hiY = cy - s * 0.075
  for (let y = 0; y < s; y++) {
    for (let x = 0; x < s; x++) {
      const i = (y * s + x) * 4
      const px = x + 0.5
      const py = y + 0.5
      if (sdfRoundRect(px, py, s, cornerR) > 0) continue // transparent corners
      const dA = Math.hypot(px - cx, py - ay)
      const dB = Math.hypot(px - cx, py - by)
      const insideLens = dA <= R && dB <= R
      let rgb = mix(BG_TOP, BG_BOTTOM, py / s) // ink square, subtle top light
      if (insideLens) {
        // sclera: cream, lighter at top, with a soft shadow cast by the upper lid
        rgb = mix(SCLERA_TOP, SCLERA_BOTTOM, clamp01((py - (cy - h)) / (2 * h)))
        rgb = mix(rgb, EYELID_SHADOW, smooth(1 - (R - dB) / (h * 0.7)) * 0.16)
        const di = Math.hypot(px - cx, py - cy)
        if (di <= irisR) {
          rgb = mix(IRIS_IN, IRIS_OUT, smooth(di / irisR)) // radial iris
          if (di > irisR - rim * 1.6) {
            rgb = mix(rgb, IRIS_RIM, smooth((di - (irisR - rim * 1.6)) / (rim * 1.6)) * 0.9)
          }
        }
        if (di <= pupilR) rgb = PUPIL
        const dHi = Math.hypot(px - hiX, py - hiY)
        if (dHi <= hiR * 1.6) rgb = mix(rgb, WHITE, smooth(1 - dHi / (hiR * 1.6))) // soft catchlight
      }
      // peach rim traces the almond outline (straddles the lens boundary)
      const onLower = Math.abs(dA - R) <= rim && dB <= R + rim
      const onUpper = Math.abs(dB - R) <= rim && dA <= R + rim
      if (onLower || onUpper) rgb = PEACH
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
