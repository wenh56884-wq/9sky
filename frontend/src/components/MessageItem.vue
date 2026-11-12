<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'
import MarkdownView from './MarkdownView.vue'
import PlanPanel from './PlanPanel.vue'
import StatusLine from './StatusLine.vue'
import ApprovalCard from './ApprovalCard.vue'
import DeepTrace from './DeepTrace.vue'
import SourceCard from './SourceCard.vue'

const props = defineProps({
  message: { type: Object, required: true },
})

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
</script>

<template>
  <div v-if="message.role === 'user'" class="msg user">
    <div class="user-bubble">{{ message.content }}</div>
  </div>

  <div v-else class="msg assistant">
    <div class="avatar">梧</div>
    <div class="ai-box">
      <div class="role">九天梧桐 <span v-if="time" class="time"> · {{ time }}</span></div>

      <PlanPanel v-if="message.plan" :plan="message.plan" />
      <StatusLine v-if="message.status" :status="message.status" />
      <ApprovalCard v-for="a in message.approvals" :key="a.approval_id" :approval="a" />
      <DeepTrace v-if="message.trace" :trace="message.trace" />

      <div class="ai-card">
        <div v-if="message.typing && !message.content" class="ai-content">
          <span class="typing"><i></i><i></i><i></i></span>
        </div>
        <MarkdownView v-else :content="message.content" />
        <div class="msg-actions">
          <button type="button" class="mini-btn" title="复制回答" @click="copy">
            <svg v-if="!copied" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            {{ copied ? '已复制' : '复制' }}
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
