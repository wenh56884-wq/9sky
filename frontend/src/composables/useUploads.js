// 资料上传编排：面板开关、文件列表、上传、删除、预览、令牌、toast
import { reactive, readonly } from 'vue'
import { asJson, upQuery, authFetch } from '../api'

const state = reactive({
  panelOpen: false,
  token: '',
  files: [],
  directory: '',
  memory: {},
  loading: false,
  // 预览弹窗
  previewOpen: false,
  previewName: '',
  preview: null,   // { name, kind, sheets, text, truncated, message }
  previewLoading: false,
})

function toast(text) {
  const node = document.createElement('div')
  node.className = 'up-toast'
  node.textContent = text
  document.body.appendChild(node)
  setTimeout(() => node.remove(), 2600)
}

function openPanel() {
  state.panelOpen = true
  loadUploads()
}

function closePanel() {
  state.panelOpen = false
}

function fmtSize(bytes) {
  const n = Number(bytes) || 0
  return n >= 1024 * 1024 ? (n / 1024 / 1024).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB'
}

function setToken(v) {
  state.token = (v || '').trim()
}

async function loadUploads() {
  state.loading = true
  try {
    const data = await authFetch(upQuery('/api/uploads', state.token)).then(asJson)
    state.files = data.files || []
    state.directory = data.directory || ''
    state.memory = data.memory || {}
  } catch (err) {
    toast('读取失败：' + err.message)
  } finally {
    state.loading = false
  }
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || [])
  if (!files.length) return
  const form = new FormData()
  files.forEach((f) => form.append('file', f))
  toast('正在上传并解析…')
  try {
    const res = await authFetch(upQuery('/api/uploads', state.token), { method: 'POST', body: form })
    const data = await asJson(res)
    if (!res.ok) {
      toast('上传失败：' + (data.error || '未知错误'))
      return
    }
    const saved = data.saved || []
    const failed = data.failed || []
    if (saved.length) {
      toast('已完成：' + saved.map((s) =>
        s.kind === 'table' ? s.name + '（' + s.tables + ' 表 / ' + s.rows + ' 行）' : s.name + '（' + (s.message || s.status || '已保存') + '）'
      ).join('、'))
    }
    if (failed.length) toast('失败：' + failed.map((f) => f.name + ' ' + f.error).join('；'))
    loadUploads()
  } catch (err) {
    toast('上传失败：' + err.message)
  }
}

async function deleteUpload(name) {
  if (!confirm('删除 ' + name + '？索引与记忆会一并清理。')) return
  try {
    const res = await authFetch(upQuery('/api/uploads/' + encodeURIComponent(name), state.token), { method: 'DELETE' })
    await asJson(res)
    loadUploads()
    toast('已删除 ' + name)
  } catch (err) {
    toast('删除失败：' + err.message)
  }
}

async function openDataPreview(file) {
  state.previewOpen = true
  state.previewName = file.name
  state.previewLoading = true
  state.preview = null
  try {
    const res = await authFetch(upQuery('/api/uploads/' + encodeURIComponent(file.name) + '/preview', state.token))
    const data = await asJson(res)
    if (!res.ok) throw new Error(data.error || '读取预览失败')
    state.preview = data
  } catch (err) {
    state.preview = { name: file.name, kind: 'error', message: err.message }
  } finally {
    state.previewLoading = false
  }
}

function closeDataPreview() {
  state.previewOpen = false
  state.preview = null
}

export function useUploads() {
  return {
    state: readonly(state),
    toast,
    openPanel,
    closePanel,
    setToken,
    loadUploads,
    uploadFiles,
    deleteUpload,
    openDataPreview,
    closeDataPreview,
    fmtSize,
  }
}
