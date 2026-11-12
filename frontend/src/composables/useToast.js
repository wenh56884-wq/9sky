// 轻量 Toast：右下角堆叠，3.5s 自动消失
// toast.success(msg) / toast.error(msg) / toast.info(msg)
import { reactive } from 'vue'

const toasts = reactive([])
let _seq = 0

function remove(id) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i >= 0) toasts.splice(i, 1)
}

function push(text, type) {
  const id = ++_seq
  const item = { id, text: String(text), type, leaving: false }
  toasts.push(item)
  // 3.5s 后进入退场动画，动画结束移除
  setTimeout(() => {
    item.leaving = true
    setTimeout(() => remove(id), 220)
  }, 3500)
}

export const toast = {
  success: (msg) => push(msg, 'success'),
  error: (msg) => push(msg, 'error'),
  info: (msg) => push(msg, 'info'),
}

export function useToast() {
  return { toasts, toast }
}
