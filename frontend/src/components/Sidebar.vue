<script setup>
import { ref, computed, watch } from 'vue'
import { useConversationsStore } from '../stores/conversations'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useNav } from '../composables/useNav'
import { useHealth } from '../composables/useHealth'
import { toast } from '../composables/useToast'
import { confirm as askConfirm } from '../composables/useConfirm'
import { brand } from '../brand'

const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const auth = useAuthStore()
const nav = useNav()
const { state: health } = useHealth()

const search = ref('')
const searchEl = ref(null)

// 自动聚焦重命名输入框（<script setup> 中以 v 开头的变量即局部指令）
const vFocus = {
  mounted(el) { el.focus(); el.select() },
}

const filtered = computed(() => {
  const q = search.value.trim().toLocaleLowerCase('zh-CN')
  if (!q) return conv.list
  return conv.list.filter((c) => (c.title || '').toLocaleLowerCase('zh-CN').includes(q))
})

// N6：按日期分组——今天 / 昨天 / 近 7 天 / 更早
function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

function bucketOf(item) {
  const ts = item.updated_at || item.created_at
  if (!ts) return '更早'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return '更早'
  d.setHours(0, 0, 0, 0)
  const today = startOfToday()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const sevenAgo = new Date(today)
  sevenAgo.setDate(today.getDate() - 6)
  if (d >= today) return '今天'
  if (d >= yesterday) return '昨天'
  if (d >= sevenAgo) return '近 7 天'
  return '更早'
}

const GROUP_ORDER = ['今天', '昨天', '近 7 天', '更早']

const groups = computed(() => {
  const map = {}
  for (const key of GROUP_ORDER) map[key] = []
  for (const item of filtered.value) {
    const bucket = bucketOf(item)
    if (map[bucket]) map[bucket].push(item)
  }
  return GROUP_ORDER.filter((key) => map[key].length).map((key) => [key, map[key]])
})

// N5：Ctrl+K（全局快捷键）→ 聚焦搜索框
watch(() => nav.state.searchPulse, () => {
  const el = searchEl.value
  if (el) {
    el.focus()
    el.select()
  }
})

// Esc（全局快捷键在关闭浮层后）→ 清空搜索
watch(() => nav.state.clearSearchSignal, () => {
  search.value = ''
})

async function loadConv(id) {
  // F18：切会话时中止当前生成，避免旧流继续写入已卸载的消息
  if (chat.isSending()) chat.stop()
  chat.clearMessages()
  const data = await conv.select(id)
  if (data) chat.loadHistory(data)
}

function select(id) {
  if (id === conv.currentId) return
  loadConv(id)
}

async function createChat() {
  try {
    const c = await conv.create()
    chat.clearMessages()
    config.setThreadId(c.id)
  } catch (e) {
    toast.error('新建会话没成功：' + e.message)
  }
}

async function remove(id) {
  const target = conv.list.find((c) => c.id === id)
  if (!target) return
  const ok = await askConfirm({
    title: '删除会话',
    text: '确定删除会话「' + target.title + '」？该会话的记忆会一并清除。',
    okText: '删除',
    danger: true,
  })
  if (!ok) return
  if (chat.isSending()) chat.stop()
  const wasCurrent = await conv.remove(id)
  chat.clearMessages()
  config.setThreadId(conv.currentId)
  if (wasCurrent) {
    const data = await conv.select(conv.currentId, { silent: true })
    if (data) chat.loadHistory(data)
  }
}

async function clearAll() {
  if (!conv.list.length) { toast.info('左侧还没有会话可以清空。'); return }
  const total = conv.list.length
  const ok = await askConfirm({
    title: '清空会话',
    text: '确定清空左侧全部 ' + total + ' 个会话？\n\n会删除这些会话的聊天记录与标题，且无法恢复（跨会话长期记忆会保留）。',
    okText: '清空',
    danger: true,
  })
  if (!ok) return
  try {
    if (chat.isSending()) chat.stop()
    await conv.clearAll()
    chat.clearMessages()
    const c = await conv.create()
    config.setThreadId(c.id)
    toast.success('已清空 ' + total + ' 个会话，现在是一个全新的对话。')
  } catch (e) {
    toast.error('清空没成功：' + e.message)
  }
}

function startRename(id) {
  conv.startRename(id)
}

function commitRename(id, value) {
  const v = (value || '').trim()
  const cur = conv.list.find((c) => c.id === id)
  if (v && cur && v !== cur.title) {
    conv.rename(id, v).catch((e) => toast.error('重命名没成功：' + e.message))
  }
  conv.cancelRename()
}

function onRenameKey(e, id) {
  if (e.key === 'Enter') commitRename(id, e.target.value)
  if (e.key === 'Escape') conv.cancelRename()
}

async function logout() {
  await auth.logout()
}

function openUsers() {
  nav.setView('users')
}

function openChanges() {
  nav.setView('changes')
}
</script>

<template>
  <aside class="side">
    <div class="brand">
      <div class="logo">梧</div>
      <div>
        <b>{{ brand.name }} AI 助手</b>
        <small>业务数据 · 知识库 · 预测</small>
      </div>
    </div>

    <button type="button" class="new-chat" v-if="auth.can(2)" @click="createChat">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      新建对话
    </button>

    <label class="conv-search" aria-label="搜索历史会话">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
      <input
        ref="searchEl"
        v-model="search"
        type="search"
        placeholder="搜索会话（Ctrl + K）"
        autocomplete="off"
      >
    </label>

    <p class="conv-head">
      <span>历史会话</span>
      <span class="conv-head-right">
        <span class="count-mini" v-if="conv.list.length">{{ conv.list.length }} 个</span>
        <button type="button" class="conv-clear" v-if="auth.can(2)" title="一键清空左侧全部会话（聊天记录一并删除，长期记忆保留）" @click="clearAll">清空会话</button>
      </span>
    </p>

    <ul class="conv-list">
      <template v-for="[label, items] in groups" :key="label">
        <!-- N6：分组标题 sticky -->
        <li class="conv-group">{{ label }}</li>
        <li
          v-for="item in items"
          :key="item.id"
          class="conv"
          :class="{ active: item.id === conv.currentId }"
        >
          <input
            v-if="conv.renamingId === item.id"
            class="conv-title-input"
            :value="item.title"
            @keydown="(e) => onRenameKey(e, item.id)"
            @blur="commitRename(item.id, $event.target.value)"
            v-focus
          />
          <span
            v-else
            class="conv-title"
            :title="[item.title, item.message_count + ' 条消息', '双击重命名'].join(' · ')"
            @click="select(item.id)"
            @dblclick="startRename(item.id)"
          >{{ item.title }}</span>
          <button type="button" class="conv-del" v-if="auth.can(2)" title="删除会话" @click.stop="remove(item.id)">×</button>
        </li>
      </template>
      <li v-if="!filtered.length && search" class="no-conversations">没有匹配的会话</li>
    </ul>

    <div class="side-nav" v-if="auth.can(2)">
      <button type="button" class="side-nav-btn" @click="nav.openApprovalCenter()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/></svg>
        审批中心
        <span v-if="nav.state.approvalPending" class="nav-badge">{{ nav.state.approvalPending }}</span>
      </button>
      <!-- N9：变更历史入口（管理员/超管，接口需 role ≥ 2） -->
      <button type="button" class="side-nav-btn" @click="openChanges">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg>
        变更历史
      </button>
      <button type="button" class="side-nav-btn" v-if="auth.isSuper" @click="openUsers">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        用户管理
      </button>
    </div>

    <div class="side-foot">
      <div class="user-chip">
        <span class="user-name">{{ auth.user ? auth.user.username : '' }}</span>
        <span class="user-role">{{ ROLE_LABELS[auth.role] || '访客' }}</span>
        <button type="button" class="user-logout" title="退出登录" @click="logout">登出</button>
      </div>
      <div class="status-line" :class="{ off: !health.ok }">
        <span class="dot"></span>
        <span>{{ health.sideText }}</span>
      </div>
      <div>3 个 MySQL 业务库 · RAG 知识库 · Sklearn 预测 · 跨会话记忆</div>
    </div>
  </aside>
</template>
