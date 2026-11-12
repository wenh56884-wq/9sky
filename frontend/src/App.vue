<script setup>
import { onMounted, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatHeader from './components/ChatHeader.vue'
import MessageList from './components/MessageList.vue'
import Composer from './components/Composer.vue'
import UploadPanel from './components/UploadPanel.vue'
import DataPreview from './components/DataPreview.vue'
import SourceDrawer from './components/SourceDrawer.vue'
import ApprovalCenter from './components/ApprovalCenter.vue'
import ToastHost from './components/ToastHost.vue'
import ConfirmHost from './components/ConfirmHost.vue'
import LoginView from './views/LoginView.vue'
import UserManage from './views/UserManage.vue'
import { useAuthStore } from './stores/auth'
import { useConversationsStore } from './stores/conversations'
import { useChatStore } from './stores/chat'
import { useConfigStore } from './stores/config'
import { useNav } from './composables/useNav'
import { useHealth } from './composables/useHealth'

const auth = useAuthStore()
const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const nav = useNav()
const { refreshHealth } = useHealth()

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
  </div>

  <!-- U1：全局 Toast 与确认弹窗（任何视图可用） -->
  <ToastHost />
  <ConfirmHost />
</template>
