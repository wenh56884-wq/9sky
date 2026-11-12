// Promise 式确认弹窗：const ok = await confirm({title, text, okText, danger})
// 规则：Esc = 取消，遮罩点击 = 取消，打开时焦点在"取消"，删除类按钮用 --danger
import { reactive } from 'vue'

const state = reactive({
  open: false,
  title: '',
  text: '',
  okText: '确定',
  cancelText: '取消',
  danger: false,
})

let _resolve = null

export function confirm(opts = {}) {
  return new Promise((resolve) => {
    state.title = opts.title || '请确认'
    state.text = opts.text || ''
    state.okText = opts.okText || '确定'
    state.cancelText = opts.cancelText || '取消'
    state.danger = !!opts.danger
    _resolve = resolve
    state.open = true
  })
}

function settle(result) {
  if (!state.open) return
  state.open = false
  const resolve = _resolve
  _resolve = null
  if (resolve) resolve(result)
}

export function useConfirm() {
  return {
    state,
    confirm,
    resolveOk: () => settle(true),
    resolveCancel: () => settle(false),
  }
}
