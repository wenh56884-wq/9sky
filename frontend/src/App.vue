<script setup>
import { onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatHeader from './components/ChatHeader.vue'
import MessageList from './components/MessageList.vue'
import Composer from './components/Composer.vue'
import UploadPanel from './components/UploadPanel.vue'
import DataPreview from './components/DataPreview.vue'
import SourceDrawer from './components/SourceDrawer.vue'
import { useConversationsStore } from './stores/conversations'
import { useChatStore } from './stores/chat'
import { useConfigStore } from './stores/config'
import { useHealth } from './composables/useHealth'

const conv = useConversationsStore()
const chat = useChatStore()
const config = useConfigStore()
const { refreshHealth } = useHealth()

// 初始化：拉会话列表 → 恢复上次会话（或选第一个 / 新建）→ 刷新健康状态
onMounted(async () => {
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
})
</script>

<template>
  <div class="app">
    <Sidebar />
    <main class="chat">
      <ChatHeader />
      <MessageList />
      <Composer />
      <UploadPanel />
      <DataPreview />
      <SourceDrawer />
    </main>
  </div>
</template>
