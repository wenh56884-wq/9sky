<script setup>
// N9 变更历史页：GET /api/writes/history（管理员/超管），表格展示 + 按状态筛选
import { ref, onMounted } from 'vue'
import { request } from '../api'
import { useNav } from '../composables/useNav'
import { useAuthStore } from '../stores/auth'
import { toast } from '../composables/useToast'

const nav = useNav()
const auth = useAuthStore()

const items = ref([])
const loading = ref(false)
const error = ref('')
const status = ref('')          // '' = 全部
const offset = ref(0)
const pageSize = 50
const hasMore = ref(true)

const FILTERS = [
  { key: '', label: '全部' },
  { key: 'applied', label: '已应用' },
  { key: 'reverted', label: '已撤销' },
  { key: 'failed', label: '失败' },
  { key: 'rejected', label: '已拒绝' },
]

const STATUS_LABELS = {
  applied: '已应用',
  reverted: '已撤销',
  failed: '失败',
  rejected: '已拒绝',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const q = new URLSearchParams()
    q.set('limit', String(pageSize))
    q.set('offset', String(offset.value))
    if (status.value) q.set('status', status.value)
    const data = await request('/api/writes/history?' + q.toString())
    const list = data.items || []
    items.value = offset.value ? items.value.concat(list) : list
    hasMore.value = list.length >= pageSize
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function setStatus(key) {
  if (status.value === key) return
  status.value = key
  offset.value = 0
  items.value = []
  load()
}

function loadMore() {
  offset.value += pageSize
  load()
}

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '—'
}

function target(it) {
  return (it.db_name || '—') + '.' + (it.table_name || '—')
}

function back() {
  nav.setView('workbench')
}

// ---- 写权限配置（仅超级管理员）：默认全部拒绝，显式开启的表才受理写草案 ----
const wlText = ref('{}')
const wlBusy = ref(false)
const wlError = ref('')
const wlMsg = ref('')
const wlCount = ref(0)

async function loadWhitelist() {
  if (!auth.isSuper) return
  wlError.value = ''
  wlMsg.value = ''
  try {
    const data = await request('/api/writes/whitelist')
    const wl = data.table_whitelist || {}
    wlText.value = JSON.stringify(wl, null, 2)
    wlCount.value = Object.keys(wl).length
  } catch (e) {
    wlError.value = e.message
  }
}

async function saveWhitelist() {
  wlError.value = ''
  wlMsg.value = ''
  let parsed
  try {
    parsed = JSON.parse(wlText.value || '{}')
  } catch (e) {
    wlError.value = 'JSON 格式不正确：' + e.message
    return
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    wlError.value = '配置必须是对象：{"库名.表名": {"columns": ["允许列"]}}'
    return
  }
  wlBusy.value = true
  try {
    const data = await request('/api/writes/whitelist', {
      method: 'PUT',
      body: JSON.stringify({ table_whitelist: parsed }),
    })
    const wl = data.table_whitelist || {}
    wlText.value = JSON.stringify(wl, null, 2)
    wlCount.value = Object.keys(wl).length
    wlMsg.value = '已保存并生效'
    toast.success('写权限配置已更新')
  } catch (e) {
    wlError.value = e.message
  } finally {
    wlBusy.value = false
  }
}

onMounted(() => {
  load()
  loadWhitelist()
})
</script>

<template>
  <div class="ch-wrap">
    <div class="ch-head">
      <button type="button" class="ch-back" @click="back">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>
        返回工作台
      </button>
      <span class="ch-title">变更历史</span>
      <div class="ch-filters">
        <button
          v-for="f in FILTERS"
          :key="f.key"
          type="button"
          class="ch-filter"
          :class="{ on: status === f.key }"
          @click="setStatus(f.key)"
        >{{ f.label }}</button>
      </div>
    </div>

    <div class="ch-body">
      <!-- 写权限配置（超管）：默认拒绝，显式列出的表才允许 Agent 提交写草案 -->
      <details v-if="auth.isSuper" class="ch-wl">
        <summary>写权限配置（超级管理员）· 已开启 {{ wlCount }} 张表</summary>
        <p class="ch-wl-hint">
          默认全部拒绝。只有在此显式列出的表，Agent 的写草案才会受理（受理后仍需按风险等级审批，L1 本人 / L2 管理员 / L3 超管）。
          格式：<code>{"库名.表名": {"columns": ["允许列"]}}</code>；保存 <code>{}</code> 恢复全部拒绝。
        </p>
        <textarea v-model="wlText" class="ch-wl-text" spellcheck="false" rows="8" aria-label="写表白名单 JSON"></textarea>
        <div class="ch-wl-actions">
          <button type="button" class="onb-btn" :disabled="wlBusy" @click="saveWhitelist">
            {{ wlBusy ? '保存中…' : '保存并生效' }}
          </button>
          <button type="button" class="ch-filter" @click="loadWhitelist">重新载入</button>
          <span v-if="wlError" class="ch-wl-error">{{ wlError }}</span>
          <span v-else-if="wlMsg" class="ch-wl-ok">{{ wlMsg }}</span>
        </div>
      </details>

      <p v-if="error" class="ch-empty" style="color: var(--err)">{{ error }}</p>
      <p v-else-if="loading && !items.length" class="ch-empty">加载中…</p>
      <p v-else-if="!items.length" class="ch-empty">暂无变更记录</p>

      <table v-else class="ch-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>操作人</th>
            <th>审批人</th>
            <th>变更对象</th>
            <th>操作</th>
            <th>行数</th>
            <th>状态</th>
            <th>SQL</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in items" :key="it.id">
            <td class="ch-time">{{ fmt(it.applied_at || it.created_at) }}</td>
            <td>{{ it.actor_name || '—' }}</td>
            <td>{{ it.approver_name || '—' }}</td>
            <td class="ch-target">{{ target(it) }}</td>
            <td><span class="ch-op">{{ it.operation || '—' }}</span></td>
            <td class="ch-num">
              {{ it.affected_rows != null ? it.affected_rows : '—' }}
              <span v-if="it.estimated_rows != null" class="ch-est">/ 预估 {{ it.estimated_rows }}</span>
            </td>
            <td>
              <span class="ch-status" :class="it.status">{{ STATUS_LABELS[it.status] || it.status || '—' }}</span>
            </td>
            <td>
              <details class="ch-sql-wrap">
                <summary>查看 SQL</summary>
                <pre class="ch-sql">{{ it.sql_text || '' }}</pre>
              </details>
            </td>
          </tr>
        </tbody>
      </table>

      <button v-if="hasMore" type="button" class="ch-more onb-btn" :disabled="loading" @click="loadMore">
        {{ loading ? '加载中…' : '加载更多' }}
      </button>
    </div>
  </div>
</template>
