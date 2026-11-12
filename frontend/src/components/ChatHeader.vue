<script setup>
import { computed } from 'vue'
import { useConversationsStore } from '../stores/conversations'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useHealth } from '../composables/useHealth'
import { useUploads } from '../composables/useUploads'

const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const auth = useAuthStore()
const { state: health, refreshHealth } = useHealth()
const { openPanel } = useUploads()

async function logout() {
  await auth.logout()
}

const ICON_MOON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>'
const ICON_SUN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'

const title = computed(() => (conv.current ? conv.current.title : '未选择会话'))

const count = computed(() => {
  if (!conv.current) return ''
  const n = conv.current.message_count != null ? conv.current.message_count : chat.messages.length
  return n + ' 条消息'
})

const dark = computed(() => config.isDark)

// 重命名：触发侧栏当前会话的内联编辑（与原顶栏“重命名”按钮一致）
function rename() {
  if (!conv.currentId) return
  conv.startRename(conv.currentId)
}

// 删除：等价原 removeConversation，删后选第一个或新建
async function remove() {
  const cur = conv.current
  if (!cur) return
  if (!confirm('确定删除会话「' + cur.title + '」？该会话的记忆会一并清除。')) return
  await conv.remove(cur.id)
  config.setThreadId('')
  chat.clearMessages()
  if (conv.list.length) {
    const data = await conv.select(conv.list[0].id, { silent: true })
    if (data) chat.loadHistory(data)
  } else {
    const c = await conv.create()
    config.setThreadId(c.id)
    chat.clearMessages()
  }
}
</script>

<template>
  <div class="chat-head">
    <span class="title">{{ title }}</span>
    <span class="count">{{ count }}</span>
    <span
      class="badge-btn"
      :class="health.ok ? 'on' : 'off'"
      title="后端健康状态（数据技能卡 / 深度搜索）"
      @click="refreshHealth"
    >
      <span class="dot"></span>
      <span>{{ health.text }}</span>
    </span>
    <button
      class="icon-btn"
      type="button"
      :title="dark ? '切换到浅色模式' : '切换到深色模式'"
      v-html="dark ? ICON_SUN : ICON_MOON"
      @click="config.toggleTheme"
    ></button>
    <button class="head-btn" type="button" v-if="auth.can(2)" @click="rename">重命名</button>
    <button class="head-btn danger" type="button" v-if="auth.can(2)" @click="remove">删除</button>
    <button class="head-btn" type="button" v-if="auth.can(2)" title="上传表格、文档或图片，之后可直接向 AI 提问" @click="openPanel">资料</button>
    <span class="head-user">
      <span class="head-user-name">{{ auth.user ? auth.user.username : '' }}</span>
      <span class="head-user-role">{{ ROLE_LABELS[auth.role] || '访客' }}</span>
      <button type="button" class="head-user-out" title="退出登录" @click="logout">登出</button>
    </span>
  </div>
</template>
