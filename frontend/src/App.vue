<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatHeader from './components/ChatHeader.vue'
import MessageList from './components/MessageList.vue'
import Composer from './components/Composer.vue'
import UploadPanel from './components/UploadPanel.vue'
import DataPreview from './components/DataPreview.vue'
import SourceDrawer from './components/SourceDrawer.vue'
import ApprovalCenter from './components/ApprovalCenter.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'
import OnboardingWizard from './components/OnboardingWizard.vue'
import ToastHost from './components/ToastHost.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import LoginView from './views/LoginView.vue'
import UserManage from './views/UserManage.vue'
import ChangeHistory from './views/ChangeHistory.vue'
import { useAuthStore } from './stores/auth'
import { useConversationsStore } from './stores/conversations'
import { useChatStore } from './stores/chat'
import { useConfigStore } from './stores/config'
import { useNav } from './composables/useNav'
import { useHealth } from './composables/useHealth'
import { useSourceDrawer } from './composables/useSourceDrawer'

const auth = useAuthStore()
const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const nav = useNav()
const { refreshHealth } = useHealth()
const sourceDrawer = useSourceDrawer()

let inited = false

// 初始化：拉会话列表 → 恢复上次会话（或选第一个 / 新建）→ 刷新健康状态
async function initWorkspace() {
  if (inited || !auth.loggedIn) return
  inited = true
  try {
    await conv.refresh()
  } catch (_) {
    // 后端未就绪：仍尝试按本地记录恢复，避免白屏
  }
  try {
    const saved = config.threadId
    if (saved && conv.list.some((c) => c.id === saved)) {
      const data = await conv.select(saved, { silent: true })
      if (data) chat.loadHistory(data)
    } else if (conv.list.length) {
      const data = await conv.select(conv.list[0].id, { silent: true })
      if (data) chat.loadHistory(data)
    } else {
      const c = await conv.create()
      config.setThreadId(c.id)
      chat.clearMessages()
    }
  } catch (_) {
    // 恢复失败时保持空状态，用户可手动新建
  }
  refreshHealth()
}

onMounted(async () => {
  auth.init()
  // 刷新后校验本地令牌
  if (auth.loggedIn) {
    try {
      await auth.refreshMe()
    } catch (_) {
      // 401 已由请求层拦截器处理（清登录 → 显示登录页）
    }
  }
  await initWorkspace()
})

// 登录成功后进入工作台（LoginView 登录后不会重跑 onMounted，这里监听）
watch(() => auth.loggedIn, (v) => {
  if (v) initWorkspace()
})

// ---- N4 全局快捷键 ----
const ONB_KEY = 'jtwt_onboarding'
const onbDone = ref(false)
onMounted(() => {
  try { onbDone.value = localStorage.getItem(ONB_KEY) === '1' } catch (_) {}
})
function finishOnboarding() {
  onbDone.value = true
  try { localStorage.setItem(ONB_KEY, '1') } catch (_) {}
}

function isEditable(el) {
  if (!el || !el.tagName) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable === true
}

function onGlobalKey(e) {
  if (!auth.loggedIn) return
  const editable = isEditable(e.target)
  const mod = e.ctrlKey || e.metaKey

  // Ctrl+K：打开会话搜索（输入框聚焦时不劫持，先检查事件目标）
  if (mod && (e.key === 'k' || e.key === 'K')) {
    if (editable) return
    e.preventDefault()
    nav.requestSearchFocus()
    return
  }

  // Ctrl+/：打开设置抽屉
  if (mod && e.key === '/') {
    e.preventDefault()
    nav.openSettings()
    return
  }

  // Esc：关闭所有浮层（抽屉、模态、搜索）
  if (e.key === 'Escape') {
    let closed = false
    if (nav.state.auditOpen) { nav.closeAudit(); closed = true }
    if (nav.state.settingsOpen) { nav.closeSettings(); closed = true }
    if (nav.state.approvalCenterOpen) { nav.closeApprovalCenter(); closed = true }
    if (sourceDrawer.state.open) { sourceDrawer.close(); closed = true }
    if (closed) return
    // 浮层已关：清空侧栏搜索词（搜索框本身聚焦时也清掉）
    nav.requestClearSearch()
  }
}

onMounted(() => document.addEventListener('keydown', onGlobalKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onGlobalKey))
</script>

<template>
  <LoginView v-if="!auth.loggedIn" />

  <!-- 访客（role 0）登录后无工作台权限 -->
  <div v-else-if="!auth.can(1)" class="no-access">
    <div class="no-access-card">
      <b>当前账号为访客</b>
      <p>访客仅能访问登录与健康状态，无法进入工作台。请联系超级管理员调整角色。</p>
      <button type="button" class="login-cancel" @click="auth.logout()">退出登录</button>
    </div>
  </div>

  <!-- 用户管理页（超管） -->
  <UserManage v-else-if="nav.state.view === 'users'" />

  <!-- N9 变更历史页（管理员/超管） -->
  <ChangeHistory v-else-if="nav.state.view === 'changes'" />

  <!-- 工作台 -->
  <div v-else class="app">
    <Sidebar />
    <main class="chat">
      <ChatHeader />
      <MessageList />
      <Composer />
      <UploadPanel />
      <DataPreview />
      <SourceDrawer />
    </main>
    <ApprovalCenter />
    <!-- N3 设置抽屉 -->
    <SettingsDrawer />
    <!-- E4 首启动引导：未完成时显示，完成标记写入 localStorage -->
    <OnboardingWizard v-if="!onbDone" @finish="finishOnboarding" />
  </div>

  <!-- U1：全局 Toast 与确认弹窗（任何视图可用） -->
  <ToastHost />
  <ConfirmHost />
</template>
