// 后端健康状态（Sidebar 状态脚 + ChatHeader 徽标共用）
import { reactive, readonly } from 'vue'
import { request } from '../api'

const state = reactive({
  ok: false,
  text: '连接中',
  sideText: '正在连接服务…',
  loading: false,
})

function parseHealth(data) {
  const db = data.database || {}
  const dbList = Array.isArray(db.databases) ? db.databases : []
  const dbTotal = 3
  const ready = db.ok && dbList.length > 0 ? dbList.length : 0
  const rag = data.rag || {}
  const ragOk = !!rag.enabled || !!rag.built
  const ragEngine = rag.backend ? ' · ' + rag.backend : ''
  const on = ready > 0
  return {
    ok: !!data.ok && on,
    text: '服务正常 · ' + ready + '/' + dbTotal + ' 库已连' + (ragOk ? ' · RAG 就绪' : '') + ragEngine,
    sideText: '服务正常 · ' + ready + '/' + dbTotal + ' 库已连' + (ragOk ? ' · RAG 就绪' : ''),
  }
}

async function refreshHealth() {
  state.loading = true
  try {
    const data = await request('/api/health')
    Object.assign(state, parseHealth(data))
  } catch (_) {
    state.ok = false
    state.text = '服务离线'
    state.sideText = '服务离线（python web.py）'
  } finally {
    state.loading = false
  }
}

export function useHealth() {
  return { state: readonly(state), refreshHealth }
}
