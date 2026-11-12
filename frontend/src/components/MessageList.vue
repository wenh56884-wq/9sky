<script setup>
import { ref, watch, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageItem from './MessageItem.vue'

const chat = useChatStore()
const scrollEl = ref(null)
const userScrolledUp = ref(false)
let raf = 0

const isEmpty = computed(() => chat.messages.length === 0)

const GREETINGS = [
  { until: 5, hi: '夜深了，我是九天梧桐', sub: '还没休息？有事说一声，我随时在。' },
  { until: 9, hi: '早上好，我是九天梧桐', sub: '新的一天，把问题丢给我：查数、翻资料、做预测都行。' },
  { until: 12, hi: '上午好，我是九天梧桐', sub: '把业务问题直接问出来，我来查数、检索资料、做预测、记住你的偏好。' },
  { until: 14, hi: '中午好，我是九天梧桐', sub: '午休也能问两句，查数据、找政策我都在。' },
  { until: 18, hi: '下午好，我是九天梧桐', sub: '下午适合出结论，要不要我先把数据整一整？' },
  { until: 23, hi: '晚上好，我是九天梧桐', sub: '晚上好，复盘今天的数据、做份预测，随时说。' },
  { until: 24, hi: '夜深了，我是九天梧桐', sub: '夜深了，有事说一声，剩下的交给我。' },
]
const greeting = computed(() => {
  const hour = new Date().getHours()
  return GREETINGS.find((g) => hour < g.until) || GREETINGS[0]
})

const CAPS = [
  { icon: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h3M18 14h3M14 17v3M17 18h3"/>', label: '数据库直查' },
  { icon: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>', label: '知识库问答' },
  { icon: '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>', label: '机器学习预测' },
  { icon: '<path d="M12 3a5 5 0 0 0-5 5v2H6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-1V8a5 5 0 0 0-5-5Z"/>', label: '跨会话记忆' },
]

const CHIPS = [
  { text: '医疗库 2025 年每月总收入趋势', tip: '自然语言直接查三个业务库' },
  { text: '预测医疗库未来 6 个月的收入并生成报告', tip: 'Sklearn 月度预测 + Markdown 报告' },
  { text: '三个数据库分别预测并生成预测报告', tip: '一键跑全部库默认指标' },
  { text: '记住：我喜欢简洁的回答', tip: '跨会话长期记忆，新会话也生效' },
]

function onScroll() {
  const el = scrollEl.value
  if (!el) return
  userScrolledUp.value = el.scrollTop + el.clientHeight < el.scrollHeight - 90
}

function scrollBottom(force) {
  const el = scrollEl.value
  if (!el) return
  if (!force && userScrolledUp.value) return
  if (raf) return
  raf = requestAnimationFrame(() => {
    raf = 0
    el.scrollTop = el.scrollHeight
  })
}

// 消息变化后滚动：用户新消息强制到底，流式更新遵循“是否在底部”
watch(
  () => chat.messages,
  (list) => {
    const last = list && list[list.length - 1]
    scrollBottom(last && last.role === 'user')
  },
  { deep: true, flush: 'post' }
)

function sendChip(text) {
  chat.sendQuestion(text)
}
</script>

<template>
  <section id="messages" ref="scrollEl" aria-live="polite" @scroll="onScroll">
    <div class="msgs-inner">
      <div class="empty" :class="{ show: isEmpty }">
        <div class="hero">
          <div class="big-logo">梧</div>
          <h2>{{ greeting.hi }}</h2>
          <p class="sub">{{ greeting.sub }}</p>
          <div class="caps">
            <span v-for="c in CAPS" :key="c.label" class="cap">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" v-html="c.icon"></svg>
              {{ c.label }}
            </span>
          </div>
        </div>
        <div class="sug-label">试试这样问</div>
        <div class="chips">
          <button v-for="c in CHIPS" :key="c.text" type="button" class="chip" @click="sendChip(c.text)">
            {{ c.text }}<span class="chip-tip">{{ c.tip }}</span>
          </button>
        </div>
      </div>

      <MessageItem v-for="m in chat.messages" :key="m.id" :message="m" />
    </div>
  </section>
</template>
