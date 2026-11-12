<script setup>
import { ref, computed, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useConversationsStore } from '../stores/conversations'
import { useConfigStore } from '../stores/config'
import { request } from '../api'

const chat = useChatStore()
const conv = useConversationsStore()
const config = useConfigStore()

const text = ref('')
const input = ref(null)
const skillEl = ref(null)
const modelEl = ref(null)

const sending = computed(() => chat.sending)
const canSend = computed(() => !sending.value && text.value.trim().length > 0 && !!conv.currentId)

function autoResize() {
  const el = input.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 168) + 'px'
}

function onInput() {
  autoResize()
}

function onKeydown(e) {
  if (e.key !== 'Enter' || e.shiftKey) return
  // F10：中文输入法合成中（拼音选词）回车不发送
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  if (canSend.value) submit()
}

function submit() {
  const t = text.value.trim()
  if (!canSend.value) return
  chat.sendQuestion(t)
  text.value = ''
  autoResize()
}

function stop() {
  chat.stop()
}

// 技能卡下拉：后端 /api/skills 动态下发
onMounted(async () => {
  try {
    const data = await request('/api/skills')
    const sel = skillEl.value
    if (!sel) return
    ;(data.skills || []).forEach((s) => {
      if (s.ready === false) return
      const opt = document.createElement('option')
      opt.value = s.key
      opt.textContent = s.title
      sel.appendChild(opt)
    })
    // 若已存技能不在列表中，回退为自动识别
    const has = [...sel.options].some((o) => o.value === config.skill)
    if (!has) {
      config.setSkill('')
    }
  } catch (_) { /* 后端暂不可用：保留“自动识别”单项 */ }
})

// 模型下拉：后端 /api/models 白名单
onMounted(async () => {
  try {
    const data = await request('/api/models')
    const sel = modelEl.value
    if (!sel) return
    sel.innerHTML = ''
    ;(data.models || []).forEach((id) => {
      const opt = document.createElement('option')
      opt.value = id
      opt.textContent = id
      sel.appendChild(opt)
    })
    const saved = config.model
    sel.value = (data.models || []).includes(saved) ? saved : (data.default || (data.models || [])[0] || '')
    config.setModel(sel.value)
  } catch (_) {
    if (modelEl.value) modelEl.value.innerHTML = '<option value="">模型：配置不可用</option>'
  }
})
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <div class="composer-wrap">
      <div class="composer-inner">
        <textarea
          id="question"
          ref="input"
          v-model="text"
          rows="1"
          placeholder="给九天梧桐发送消息…（Enter 发送，Shift+Enter 换行）"
          aria-label="问题"
          @input="onInput"
          @keydown="onKeydown"
        ></textarea>
        <div class="composer-bar">
          <select
            id="skill"
            ref="skillEl"
            :value="config.skill"
            class="skill-select"
            :class="{ on: !!config.skill }"
            :disabled="config.deepMode"
            aria-label="技能卡（手动指定处理方式）"
            title="手动指定技能卡：回答将优先按所选技能或库执行；留空则自动识别"
            @change="config.setSkill($event.target.value)"
          >
            <option value="">技能卡：自动识别</option>
          </select>

          <select
            id="model"
            ref="modelEl"
            :value="config.model"
            class="skill-select model-select"
            :class="{ on: !!config.model }"
            aria-label="模型"
            title="仅列出强推理与强代码模型"
            @change="config.setModel($event.target.value)"
          >
            <option value="">模型：加载中…</option>
          </select>

          <label class="proc-toggle" :class="{ on: config.showProc }">
            <input type="checkbox" :checked="config.showProc" @change="config.setShowProc($event.target.checked)" />
            显示过程
          </label>

          <label class="proc-toggle" :class="{ on: config.deepMode }">
            <input type="checkbox" :checked="config.deepMode" @change="config.setDeepMode($event.target.checked)" />
            深度搜索
          </label>

          <span class="hint">技能卡 = 指定库或能力执行 · 深度搜索 = 多轮检索综合回答</span>

          <button type="submit" class="send" :class="{ loading: sending }" :disabled="!canSend" aria-label="发送">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none"><path d="M4.5 19.5 20 12 4.5 4.5l2.1 7.5-2.1 7.5Z" fill="currentColor"/></svg>
          </button>
          <button type="button" class="stop" :class="{ show: sending }" aria-label="停止生成" title="停止生成" @click="stop">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg>
          </button>
        </div>
      </div>
    </div>
  </form>
</template>
