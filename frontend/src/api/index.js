// API 封装：统一 fetch、JSON 解析、鉴权令牌、NDJSON 流式读取

// ---- 认证令牌（由 auth store 注入）----
// 请求层持有令牌并自动带 Authorization: Bearer；401 时清令牌并回调 auth store 跳登录
let _token = ''
let _onUnauthorized = null

export function setToken(v) {
  _token = (v || '').trim()
}

export function getToken() {
  return _token
}

// 注册 401 回调（auth store 调用：清 token / 用户，让 App 回到登录页）
export function onUnauthorized(cb) {
  _onUnauthorized = cb
}

function authHeaders(extra) {
  const headers = { ...(extra || {}) }
  if (_token) headers['Authorization'] = 'Bearer ' + _token
  return headers
}

function handleUnauthorized() {
  // 只有确实带着令牌还被拒，才说明令牌失效（该回登录页）。
  // 没带令牌的匿名请求被 401 时不清登录态——否则页面初始化时若有请求抢在
  // setToken 之前发出，会把刚恢复的登录态误清掉（表现为刷新就掉登录）。
  if (!_token) return
  _token = ''
  if (typeof _onUnauthorized === 'function') _onUnauthorized()
}

// 通用 JSON 请求；非 2xx 抛出后端 error 文案；401 自动清登录
export async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: authHeaders({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401) handleUnauthorized()
    throw new Error(data.error || `请求失败（HTTP ${response.status}）`)
  }
  return data
}

// 带鉴权的 fetch（上传/预览等表单请求，返回原始 Response 由 asJson 解析）
export async function authFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers),
  })
  if (!response.ok && response.status === 401) handleUnauthorized()
  return response
}

// 把响应当 JSON 解析；不是 JSON 时把 HTTP 状态码翻成人话（典型：web.py 没重启导致 404 HTML 错误页）
export async function asJson(res) {
  const text = await res.text()
  try {
    return JSON.parse(text)
  } catch (_e) {
    const reason = res.status === 404
      ? '接口不存在——多半是 web.py 还在跑旧代码，请重启 python web.py'
      : res.status === 413 ? '文件超过上传大小上限'
      : res.status === 401 ? '登录已过期，请重新登录'
      : `服务返回了非 JSON 响应（HTTP ${res.status}）`
    throw new Error(reason)
  }
}

// 管理员令牌拼到查询串（后端设了 ADMIN_TOKEN 时写操作需要）
export function upQuery(path, token = '') {
  const t = (token || '').trim()
  return t ? (path + (path.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(t)) : path
}

// 读取 NDJSON 流（/api/chat、/api/deep）：每行一个 JSON 事件，逐行回调
// 返回最终事件（done/error）或 undefined；中断抛 AbortError 或 Error
export async function streamNdjson(url, body, onEvent, signal) {
  const response = await fetch(url, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    if (response.status === 401) handleUnauthorized()
    const data = await response.json().catch(() => ({}))
    throw new Error(data.error || `HTTP ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newline
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (!line) continue
      let event
      try { event = JSON.parse(line) } catch (_) { continue }
      if (typeof onEvent === 'function') onEvent(event)
      if (event.type === 'done' || event.type === 'error') return event
    }
  }
  throw new Error('连接已中断')
}
