// E1 多租户品牌化：从单一主色推导 brand-50~900 色阶，写入 CSS 变量
// 硬约束：租户只提供一个色值；推导函数保证深色下对比度仍达 AA
// 支持 window.__JTW_BRAND__ 运行期覆盖（main.js 初始化时读取）

const WHITE = [255, 255, 255]
const BLACK = [0, 0, 0]
const DEFAULT_PRIMARY = '#2f52e0'

function hexToRgb(hex) {
  let h = String(hex || '').trim().replace(/^#/, '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return hexToRgb(DEFAULT_PRIMARY)
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

function rgbToHex(rgb) {
  return '#' + rgb
    .map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0'))
    .join('')
}

// 混色：t 是 b 的权重（0 = a，1 = b）
function mix(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}

// 浅色阶（50-500）：主色向白色混合，数字越大越深；600 = 主色本身
const TINT = { 50: 0.95, 100: 0.88, 200: 0.76, 300: 0.62, 400: 0.46, 500: 0.30 }
// 深色阶（700-900）：主色向黑色混合
const SHADE = { 700: 0.16, 800: 0.30, 900: 0.44 }
// 深色模式提亮系数：每档再向白色混合，保证深色背景上文字/边框对比度达 AA（≥4.5:1）
const DARK_BOOST = {
  50: 0.82, 100: 0.72, 200: 0.56, 300: 0.44, 400: 0.32, 500: 0.22,
  600: 0.34, 700: 0.46, 800: 0.58, 900: 0.70,
}

export function buildBrandScale(primary) {
  const rgb = hexToRgb(primary)
  const scale = { 600: rgbToHex(rgb) }
  for (const k of Object.keys(TINT)) scale[k] = rgbToHex(mix(rgb, WHITE, TINT[k]))
  for (const k of Object.keys(SHADE)) scale[k] = rgbToHex(mix(rgb, BLACK, SHADE[k]))
  return scale
}

export function buildBrandScaleDark(primary) {
  const base = buildBrandScale(primary)
  const scale = {}
  for (let i = 50; i <= 900; i += 50) {
    const t = DARK_BOOST[i]
    scale[i] = rgbToHex(mix(hexToRgb(base[i]), WHITE, t))
  }
  return scale
}

// 当前生效的品牌（含运行期覆盖），由 initBrand 写入
let _brand = null

export function getBrand() {
  return _brand
}

// 把品牌色阶写入 :root 的 CSS 变量（--brand-50 ~ --brand-900）
// theme 传 'light' | 'dark'，跟随主题切换重算
export function applyBrand(brand, theme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const t = theme || root.dataset.theme || 'light'
  const scale = t === 'dark' ? buildBrandScaleDark(brand.primary) : buildBrandScale(brand.primary)
  for (let i = 50; i <= 900; i += 50) {
    if (scale[i]) root.style.setProperty('--brand-' + i, scale[i])
  }
}

export function initBrand(brand) {
  _brand = brand
  applyBrand(brand)
}

// 读取 window.__JTW_BRAND__ 运行期覆盖并与默认品牌合并（运维不用重新构建）
export function resolveBrand(defaultBrand) {
  const runtime = (typeof window !== 'undefined' && window.__JTW_BRAND__) || null
  return {
    name: defaultBrand.name,
    logo: defaultBrand.logo,
    primary: defaultBrand.primary,
    ...(runtime || {}),
  }
}
