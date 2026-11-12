// 来源详情抽屉（全局）：SourceCard / DeepTrace 点击来源项时打开
import { reactive, readonly } from 'vue'

const state = reactive({
  open: false,
  payload: null, // { kind, tag, title, sub, detailRows, tables, notes, sql, pills, snippet }
})

function open(payload) {
  state.payload = payload
  state.open = true
}

function close() {
  state.open = false
}

export function useSourceDrawer() {
  return { state: readonly(state), open, close }
}
