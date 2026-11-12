import { defineStore } from 'pinia'
import { useConversationsStore } from './conversations'
import { useConfigStore } from './config'
import { streamChat, streamDeep } from '../composables/useChat'

// 消息 id 生成
let _seq = 0
function nextId() {
  _seq += 1
  return 'm' + Date.now().toString(36) + '_' + _seq
}

// 当前流式控制器（非响应式，模块级单例即可）
let _controller = null

// F18：生成轮次计数器，用于切会话/新轮后丢弃旧流的写入与收尾
let runSeq = 0

// 构造一条 assistant 消息骨架
function assistantSkeleton() {
  return {
    id: nextId(),
    role: 'assistant',
    content: '',
    started: false,
    typing: true,
    createdAt: Date.now(), // 本轮新消息的本地时间（B2：仅本轮显示，历史消息没有）
    plan: null,          // { goal, steps:[], progress, thinking }
    sources: [],
    trace: null,         // 深度搜索过程 { info, plan, search, gap, rerank, fail, sources }
    status: '',
    approvals: [],
  }
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],        // 当前会话的消息数组
    sending: false,       // 是否正在生成
  }),
  getters: {
    isEmpty: (s) => s.messages.length === 0,
    lastMessage: (s) => s.messages[s.messages.length - 1] || null,
  },
  actions: {
    // 载入某会话的历史消息（来自 /api/conversations/<id>/messages）
    // 后端只返回 {role, content}，没有时间戳：历史消息不携带 createdAt，不显示时间
    setMessages(list, plan, sources) {
      this.messages = (list || []).map((m) =>
        m.role === 'assistant'
          ? {
              id: nextId(),
              role: 'assistant',
              content: m.content || '',
              started: !!m.content,
              typing: false,
              plan: plan || null,
              sources: sources || [],
            }
          : { id: nextId(), role: 'user', content: m.content || '' }
      )
    },

    // 载入某会话历史（Sidebar 切换会话时调用，含 plan / sources 恢复）
    loadHistory(data) {
      this.setMessages(data.messages, data.plan, data.sources)
    },

    // 切换到指定会话：中止当前生成 → 清空当前消息 → 拉取该会话历史并载入
    async loadConversation(id) {
      const conv = useConversationsStore()
      if (!id || id === conv.currentId) return
      if (_controller) _controller.abort()
      this.clearMessages()
      const data = await conv.select(id)
      if (data) this.loadHistory(data)
    },

    clearMessages() {
      this.messages = []
    },

    addUserMessage(text) {
      this.messages.push({ id: nextId(), role: 'user', content: text, createdAt: Date.now() })
    },

    addAssistantMessage() {
      const msg = assistantSkeleton()
      this.messages.push(msg)
      return msg
    },

    // 发送问题：编排用户消息 → assistant 消息 → 流式 → 收尾
    // F18 竞态保护：runSeq 递增标记当前轮；生成中切会话后，
    // 旧流的事件不再写入消息，finally 只在仍是当前轮时重置 sending
    async sendQuestion(text) {
      if (!text || this.sending) return
      const conv = useConversationsStore()
      const cfg = useConfigStore()
      if (!conv.currentId) return

      const myRun = ++runSeq
      const threadAtSend = conv.currentId
      const isStale = () => myRun !== runSeq || threadAtSend !== conv.currentId

      this.addUserMessage(text)
      const assistant = this.addAssistantMessage()
      this.sending = true
      _controller = new AbortController()

      try {
        const final = cfg.deepMode
          ? await streamDeep({
              question: text,
              threadId: conv.currentId,
              model: cfg.model,
              controller: _controller,
              message: assistant,
              isStale,
            })
          : await streamChat({
              question: text,
              threadId: conv.currentId,
              skill: cfg.skill,
              model: cfg.model,
              controller: _controller,
              message: assistant,
              showProc: cfg.showProc,
              isStale,
            })
        // 已切会话/已被新轮取代：不再回写线程与刷新列表
        if (isStale()) return
        // 后端可能为本轮新建了会话，回写当前 id 并持久化偏好
        if (final && final.thread_id) conv.currentId = final.thread_id
        cfg.setThreadId(conv.currentId)
        await conv.refresh()
      } catch (error) {
        // streamChat/streamDeep 内部已做错误友好化，这里只兜底防止未捕获
      } finally {
        // 只有仍是当前轮的收尾才重置发送态，避免新轮的发送态被旧流覆盖
        if (myRun === runSeq) {
          this.sending = false
          _controller = null
        }
      }
    },

    // 中止当前生成
    stop() {
      if (_controller) _controller.abort()
    },

    // 是否正在生成（供 Composer 判定发送/停止按钮）
    isSending() {
      return this.sending
    },
  },
})
