<script setup>
// E4 首启动引导：3 步向导——配 Key → 测连库 → 导知识库，每步可跳过
// 首次启动时显示（localStorage jtwt_onboarding 标记是否已完成）
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useHealth } from '../composables/useHealth'
import { useUploads } from '../composables/useUploads'
import { brand } from '../brand'

const emit = defineEmits(['finish'])

const { state: health, refreshHealth } = useHealth()
const { openPanel } = useUploads()

// ---- 第 1 步：配 Key ----
const KEY_KEY = 'jtwt_llm_key'
const keyInput = ref('')
onMounted(() => {
  try { keyInput.value = localStorage.getItem(KEY_KEY) || '' } catch (_) {}
})

function saveKey() {
  const v = keyInput.value.trim()
  try {
    v ? localStorage.setItem(KEY_KEY, v) : localStorage.removeItem(KEY_KEY)
  } catch (_) {}
}

// ---- 第 2 步：测连库 ----
const testing = ref(false)
async function testDb() {
  testing.value = true
  try {
    await refreshHealth()
  } finally {
    testing.value = false
  }
}

// ---- 步骤流转 ----
const step = ref(1)
const totalSteps = 3

function goNext() {
  if (step.value === 1) saveKey()
  if (step.value < totalSteps) step.value += 1
  else finish()
}

// 每步可跳过：跳过当前步进入下一步；已是最后一步则直接完成
function skip() {
  if (step.value < totalSteps) step.value += 1
  else finish()
}

function finish() {
  emit('finish')
}

function onKey(e) {
  if (e.key === 'Escape') finish()
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="onb-mask">
    <div class="onb-card" role="dialog" aria-modal="true" aria-label="首次启动引导">
      <div class="onb-steps">
        <span
          v-for="n in totalSteps"
          :key="n"
          class="onb-step-dot"
          :class="{ on: step === n, done: step > n }"
        ></span>
      </div>

      <template v-if="step === 1">
        <div class="onb-title">配置模型 Key</div>
        <p class="onb-desc">
          填入大模型服务的 API Key，用于问答推理。Key 保存在本机浏览器，随偏好一起持久化；
          也可以留空稍后再配，直接进入下一步。
        </p>
        <input
          v-model="keyInput"
          class="onb-input"
          type="password"
          placeholder="API Key（可留空跳过）"
          autocomplete="off"
        >
      </template>

      <template v-else-if="step === 2">
        <div class="onb-title">测试数据库连接</div>
        <p class="onb-desc">
          点击检测，确认后端与三个 MySQL 业务库、RAG 知识库的连接状态。
          检测结果与顶栏健康徽标一致。
        </p>
        <div class="onb-test-row">
          <span class="onb-status" :class="health.ok ? 'on' : 'off'">
            <span class="dot"></span>{{ health.sideText }}
          </span>
          <button type="button" class="onb-btn primary" :disabled="testing" @click="testDb">
            {{ testing ? '检测中…' : '开始检测' }}
          </button>
        </div>
      </template>

      <template v-else>
        <div class="onb-title">导入知识库</div>
        <p class="onb-desc">
          上传制度文档、表格或资料，之后可以直接向 AI 提问。需要管理员权限；
          也可以先跳过，稍后在对话中点「资料」上传。
        </p>
        <div class="onb-test-row">
          <button type="button" class="onb-btn" @click="openPanel">打开上传面板</button>
        </div>
      </template>

      <div class="onb-actions">
        <button type="button" class="onb-btn" @click="skip">跳过</button>
        <button type="button" class="onb-btn primary" @click="goNext">
          {{ step === totalSteps ? '完成' : '下一步' }}
        </button>
      </div>
      <p class="onb-foot">{{ brand.name }} · 每步都可跳过，随时结束引导</p>
    </div>
  </div>
</template>
