<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { request } from '../api'
import { useConversationsStore } from '../stores/conversations'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useHealth } from '../composables/useHealth'
import { useUploads } from '../composables/useUploads'
import { useNav } from '../composables/useNav'
import { confirm as askConfirm } from '../composables/useConfirm'
import { toast } from '../composables/useToast'
import { exportChat } from '../utils/exportChat'
import { brand } from '../brand'

const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const auth = useAuthStore()
const nav = useNav()
const { state: health, refreshHealth } = useHealth()
const { openPanel } = useUploads()

async function logout() {
  await auth.logout()
}

const ICON_MOON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>'
const ICON_SUN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
const ICON_SETTINGS = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg>'
const ICON_EXPORT = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>'
const ICON_CHEVRON = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>'

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

// 删除：等价原 removeConversation，删后选第一个或新建（B4 由 store 处理切换）
async function remove() {
  const cur = conv.current
  if (!cur) return
  const ok = await askConfirm({
    title: '删除会话',
    text: '确定删除会话「' + cur.title + '」？该会话的记忆会一并清除。',
    okText: '删除',
    danger: true,
  })
  if (!ok) return
  if (chat.isSending()) chat.stop()
  const wasCurrent = await conv.remove(cur.id)
  chat.clearMessages()
  config.setThreadId(conv.currentId)
  if (wasCurrent) {
    const data = await conv.select(conv.currentId, { silent: true })
    if (data) chat.loadHistory(data)
  }
}

// N2：导出对话为 Markdown（文件名含标题与日期）
function exportConversation() {
  if (!conv.current) { toast.info('还没有选择会话，无法导出。'); return }
  if (!chat.messages.length) { toast.info('该会话还没有消息，无需导出。'); return }
  try {
    const name = exportChat(conv.current.title, chat.messages)
    toast.success('对话已导出：' + name)
  } catch (e) {
    toast.error('导出失败：' + e.message)
  }
}

// N3：打开设置抽屉
function openSettings() {
  nav.openSettings()
}

// E5：模型切换可见——顶栏模型徽章，点击弹出模型列表，切换后立即生效
const models = ref([])
const modelOpen = ref(false)
const modelWrap = ref(null)
const currentModel = computed(() => config.model)

async function loadModels() {
  try {
    const data = await request('/api/models')
    models.value = data.models || []
    // 已存模型不在白名单时回退到默认
    if (data.default && !models.value.includes(config.model)) {
      config.setModel(data.default)
    }
  } catch (_) {
    models.value = []
  }
}

function pickModel(id) {
  config.setModel(id)
  modelOpen.value = false
  toast.success('已切换到模型 ' + id)
}

function onDocClick(e) {
  const el = modelWrap.value
  if (!el) return
  if (!el.contains(e.target)) modelOpen.value = false
}

onMounted(() => {
  loadModels()
  document.addEventListener('click', onDocClick)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
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

    <!-- E5：模型徽章 + 下拉 -->
    <div ref="modelWrap" class="model-pick" v-if="models.length">
      <button
        type="button"
        class="badge-btn model-badge"
        :class="{ on: !!currentModel }"
        title="当前模型，点击切换"
        aria-haspopup="true"
        @click="modelOpen = !modelOpen"
      >
        <span class="dot model-dot"></span>
        <span class="model-name">{{ currentModel || '模型' }}</span>
        <span v-html="ICON_CHEVRON"></span>
      </button>
      <div v-if="modelOpen" class="model-pop" role="menu">
        <button
          v-for="m in models"
          :key="m"
          type="button"
          role="menuitemradio"
          :aria-checked="m === currentModel"
          :class="{ on: m === currentModel }"
          @click="pickModel(m)"
        >{{ m }}</button>
      </div>
    </div>

    <button
      class="icon-btn"
      type="button"
      :title="dark ? '切换到浅色模式' : '切换到深色模式'"
      v-html="dark ? ICON_SUN : ICON_MOON"
      @click="config.toggleTheme"
    ></button>

    <!-- N3：设置抽屉 -->
    <button class="icon-btn" type="button" title="设置（Ctrl + /）" aria-label="设置" v-html="ICON_SETTINGS" @click="openSettings"></button>

    <!-- N2：导出对话 -->
    <button class="head-btn" type="button" title="导出当前对话为 Markdown 文件" @click="exportConversation">
      <span v-html="ICON_EXPORT"></span> 导出
    </button>

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
