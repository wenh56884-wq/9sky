<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import MarkdownView from './MarkdownView.vue'
import PlanPanel from './PlanPanel.vue'
import StatusLine from './StatusLine.vue'
import ApprovalCard from './ApprovalCard.vue'
import WriteProposalCard from './WriteProposalCard.vue'
import DeepTrace from './DeepTrace.vue'
import SourceCard from './SourceCard.vue'
import { useChatStore } from '../stores/chat'
import { useConfigStore } from '../stores/config'
import { toast } from '../composables/useToast'
import { brand } from '../brand'

const props = defineProps({
  message: { type: Object, required: true },
})

const chat = useChatStore()
const config = useConfigStore()

// B2：后端历史消息只有 {role, content}，没有时间戳。
// 只有本轮新消息（本地创建，带 createdAt）显示时间，历史消息不显示，不伪造。
function clock(d) {
  const date = d || new Date()
  return String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0')
}

const time = computed(() => {
  const t = props.message.createdAt
  return t ? clock(new Date(t)) : ''
})

// B1：用 ref 管理 copied 状态，不用全局 querySelector，不改 textContent
const copied = ref(false)
let timer = null

async function copy() {
  const text = props.message.content || ''
  try {
    await navigator.clipboard.writeText(text)
  } catch (_) {
    fallbackCopy(text)
  }
  copied.value = true
  clearTimeout(timer)
  timer = setTimeout(() => {
    copied.value = false
  }, 1500)
}

onBeforeUnmount(() => clearTimeout(timer))

function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.cssText = 'position:fixed;opacity:0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy') } catch (_) { /* noop */ }
  ta.remove()
}

// N7：复制 error_id（用户可贴给运维定位）
const errCopied = ref(false)
let errTimer = null

async function copyError() {
  const id = props.message.error_id || ''
  try {
    await navigator.clipboard.writeText(id)
  } catch (_) {
    fallbackCopy(id)
  }
  errCopied.value = true
  clearTimeout(errTimer)
  errTimer = setTimeout(() => {
    errCopied.value = false
  }, 1500)
}

onBeforeUnmount(() => clearTimeout(errTimer))

// N1 再答一次：重新发送这条回答之前最近一条用户提问。
// 文案是「再答一次」而不是「重新生成」——后端每轮追加历史，
// 叫重新生成会让用户误以为历史被替换（§11 诚实性要求）。
function reAnswer() {
  const idx = chat.messages.findIndex((m) => m.id === props.message.id)
  for (let i = idx - 1; i >= 0; i--) {
    const prev = chat.messages[i]
    if (prev.role === 'user') {
      chat.sendQuestion(prev.content)
      return
    }
  }
  toast.info('这条回答前面没有找到用户提问，无法再答一次。')
}

// N1 赞 / 踩：图标切换状态，再点一次取消
function toggleRating(v) {
  props.message.rating = props.message.rating === v ? '' : v
}
</script>

<template>
  <div v-if="message.role === 'user'" class="msg user">
    <div class="user-bubble">{{ message.content }}</div>
  </div>

  <div v-else class="msg assistant">
    <div class="avatar">梧</div>
    <div class="ai-box">
      <div class="role">{{ brand.name }} <span v-if="time" class="time"> · {{ time }}</span></div>

      <PlanPanel v-if="message.plan && config.showProc" :plan="message.plan" />
      <StatusLine v-if="message.status" :status="message.status" />
      <ApprovalCard v-for="a in message.approvals" :key="a.approval_id" :approval="a" />
      <WriteProposalCard
        v-for="p in message.proposals"
        :key="p.proposal_id"
        :proposal="p"
        :status="p.status"
        :execution="p.execution"
        @changed="(e) => { p.status = e.status; if (e.execution) p.execution = e.execution }"
      />
      <DeepTrace v-if="message.trace && config.showProc" :trace="message.trace" />

      <div class="ai-card">
        <div v-if="message.typing && !message.content" class="ai-content">
          <span class="typing"><i></i><i></i><i></i></span>
        </div>
        <MarkdownView v-else :content="message.content" />

        <!-- N7：错误气泡带 error_id，提供复制按钮 -->
        <div v-if="message.error_id" class="err-bar">
          <span>⚠ 错误编号</span>
          <code>{{ message.error_id }}</code>
          <button type="button" class="mini-btn" :title="errCopied ? '已复制' : '复制错误编号'" @click="copyError">
            {{ errCopied ? '已复制' : '复制' }}
          </button>
        </div>

        <div class="msg-actions">
          <button type="button" class="mini-btn" title="复制回答" @click="copy">
            <svg v-if="!copied" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            {{ copied ? '已复制' : '复制' }}
          </button>
          <button type="button" class="mini-btn" title="再答一次（重新发送这条提问）" @click="reAnswer">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v5h-5"/></svg>
            再答一次
          </button>
          <button
            type="button"
            class="mini-btn"
            :class="{ on: message.rating === 'up' }"
            :aria-pressed="message.rating === 'up'"
            title="赞"
            @click="toggleRating('up')"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10.5V21H4.5a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 4.5 9h2.5Z"/><path d="m7 10.5 4.2-7.1a2.2 2.2 0 0 1 2.1 1.4v3.6h6.1a2.2 2.2 0 0 1 2.2 2.7l-1.3 8.3a2.2 2.2 0 0 1-2.1 1.7H7"/></svg>
          </button>
          <button
            type="button"
            class="mini-btn"
            :class="{ on: message.rating === 'down' }"
            :aria-pressed="message.rating === 'down'"
            title="踩"
            @click="toggleRating('down')"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 13.5V3h2.5a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19.5 15h-2.5Z"/><path d="m17 13.5-4.2 7.1a2.2 2.2 0 0 1-2.1-1.4v-3.6H4.6a2.2 2.2 0 0 1-2.2-2.7l1.3-8.3a2.2 2.2 0 0 1 2.1-1.7H17"/></svg>
          </button>
        </div>
      </div>

      <!-- 普通问答数据来源 -->
      <SourceCard v-if="!message.trace && message.sources && message.sources.length" :items="message.sources" />

      <!-- 深度搜索参考来源（.deep-src 样式，位于回答下方） -->
      <div v-if="message.trace && message.trace.sources && message.trace.sources.length" class="deep-src">
        <div class="ds-title">参考来源（正文中的 [n] 即对应下方片段）</div>
        <details v-for="it in message.trace.sources" :key="(it.index ?? '') + '_' + (it.source || '')">
          <summary>
            [{{ it.index ?? '?' }}] {{ it.source || '未知文档' }}
            <template v-if="it.chunk_index != null"> · 第 {{ it.chunk_index }} 段</template>
            <template v-if="it.page"> · PDF 第 {{ it.page }} 页</template>
          </summary>
          <div class="snip">{{ it.snippet || '' }}</div>
        </details>
      </div>
    </div>
  </div>
</template>
