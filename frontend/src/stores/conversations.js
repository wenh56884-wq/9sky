import { defineStore } from 'pinia'
import { request } from '../api'

// 会话管理：列表、当前会话、新建/切换/删除/清空/重命名、拉取历史消息
export const useConversationsStore = defineStore('conversations', {
  state: () => ({
    list: [],          // 会话列表（按更新时间倒序）
    currentId: '',     // 当前会话 id
    loading: false,
    renamingId: '',    // 正在重命名的会话 id（供顶栏“重命名”按钮触发侧栏内联编辑）
  }),
  getters: {
    current: (s) => s.list.find((c) => c.id === s.currentId) || null,
  },
  actions: {
    async refresh() {
      this.loading = true
      try {
        const data = await request('/api/conversations')
        this.list = data.conversations || []
      } finally {
        this.loading = false
      }
    },
    async create() {
      const data = await request('/api/conversations', { method: 'POST', body: JSON.stringify({}) })
      this.list = [data.conversation, ...this.list]
      this.currentId = data.conversation.id
      return data.conversation
    },
    async select(id, opts = {}) {
      if (id === this.currentId && !opts.silent) return
      this.currentId = id
      // 返回该会话完整历史（含 plan / sources），供消息区渲染
      const data = await request(`/api/conversations/${id}/messages`)
      return data
    },
    async rename(id, title) {
      const data = await request(`/api/conversations/${id}`, {
        method: 'PATCH', body: JSON.stringify({ title }),
      })
      const item = this.list.find((c) => c.id === id)
      if (item && data.conversation) Object.assign(item, data.conversation)
      return data.conversation
    },
    async remove(id) {
      await request(`/api/conversations/${id}`, { method: 'DELETE' })
      const wasCurrent = this.currentId === id
      this.list = this.list.filter((c) => c.id !== id)
      // B4：删当前会话后 currentId 不再残留——自动切下一条，没有则新建空会话
      if (wasCurrent) {
        if (this.list.length) {
          this.currentId = this.list[0].id
        } else {
          const c = await this.create()
          this.currentId = c.id
        }
      }
      return wasCurrent
    },
    startRename(id) {
      this.renamingId = id || ''
    },
    cancelRename() {
      this.renamingId = ''
    },
    async clearAll() {
      const data = await request('/api/conversations', { method: 'DELETE' })
      this.list = []
      this.currentId = ''
      return data
    },
  },
})
