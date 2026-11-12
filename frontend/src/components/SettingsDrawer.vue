<script setup>
// N3 设置抽屉：主题 / 字号 / 显示过程 / 快捷键 / 服务状态
// 偏好持久化：主题与显示过程复用 config store（wh_* 键不变）；字号用新键 jtwt_font_size
// E2 审计日志：后端 audit.py 未接入，此处先留展示位占位
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useNav } from '../composables/useNav'
import { useConfigStore } from '../stores/config'
import { useHealth } from '../composables/useHealth'

const nav = useNav()
const config = useConfigStore()
const { state: health, refreshHealth } = useHealth()

const open = computed(() => nav.state.settingsOpen)

// ---- 字号：小/中/大，用 CSS 变量 --t-base 调整 ----
const FONT_KEY = 'jtwt_font_size'
const FONT_SIZES = [
  { key: 'small', label: '小', value: '13px' },
  { key: 'medium', label: '中', value: '14px' },
  { key: 'large', label: '大', value: '16px' },
]
const fontSize = ref('medium')

function applyFontSize(v) {
  fontSize.value = v
  try { localStorage.setItem(FONT_KEY, v) } catch (_) {}
  const value = (FONT_SIZES.find((f) => f.key === v) || FONT_SIZES[1]).value
  document.documentElement.style.setProperty('--t-base', value)
}

onMounted(() => {
  const saved = localStorage.getItem(FONT_KEY)
  if (saved && FONT_SIZES.some((f) => f.key === saved)) applyFontSize(saved)
})

// ---- 快捷键列表（N4 实际注册在 App.vue）----
const shortcuts = [
  { keys: 'Ctrl + K', desc: '聚焦会话搜索' },
  { keys: 'Ctrl + /', desc: '打开 / 关闭设置抽屉' },
  { keys: 'Ctrl + Enter', desc: '在输入框中发送' },
  { keys: 'Esc', desc: '关闭所有浮层' },
]

// E2：审计日志展示位（后端未接入，占位提示）——弹窗开关走 nav（全局 Esc 可统一处理）
const auditOpen = computed(() => nav.state.auditOpen)

function openAudit() {
  nav.openAudit()
}

function close() {
  nav.closeSettings()
}

function onKey(e) {
  if (e.key !== 'Escape') return
  // 审计占位弹窗优先关闭，不波及设置抽屉
  if (auditOpen.value) {
    nav.closeAudit()
    return
  }
  if (open.value) close()
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

watch(open, (v) => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = v ? 'hidden' : ''
  }
  if (v) {
    const btn = document.querySelector('.settings-drawer .st-close')
    if (btn) btn.focus()
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="settings-mask" :class="{ show: open }" @click="close"></div>
    <aside
      class="settings-drawer"
      :class="{ open }"
      role="dialog"
      aria-modal="true"
      aria-label="设置"
    >
      <div class="st-head">
        <span class="st-title">设置</span>
        <button type="button" class="st-close" title="关闭（Esc）" @click="close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>

      <div class="st-body">
        <!-- 主题 -->
        <section class="st-sec">
          <div class="st-label">主题</div>
          <div class="st-row">
            <span>外观模式</span>
            <div class="st-seg">
              <button type="button" :class="{ on: !config.isDark }" @click="config.setTheme('light')">浅色</button>
              <button type="button" :class="{ on: config.isDark }" @click="config.setTheme('dark')">深色</button>
            </div>
          </div>
        </section>

        <!-- 字号 -->
        <section class="st-sec">
          <div class="st-label">字号</div>
          <div class="st-row">
            <span>正文字号</span>
            <div class="st-seg">
              <button
                v-for="f in FONT_SIZES"
                :key="f.key"
                type="button"
                :class="{ on: fontSize === f.key }"
                @click="applyFontSize(f.key)"
              >{{ f.label }}</button>
            </div>
          </div>
          <p class="st-hint">通过 CSS 变量 --t-base 全局调整，刷新后保持。</p>
        </section>

        <!-- 显示过程 -->
        <section class="st-sec">
          <div class="st-label">显示过程</div>
          <label class="st-check">
            <input type="checkbox" :checked="config.showProc" @change="config.setShowProc($event.target.checked)" />
            <span>显示执行计划 / 深度搜索过程面板</span>
          </label>
          <p class="st-hint">关闭后聊天区只保留回答正文与数据来源，过程面板不再展示。</p>
        </section>

        <!-- 快捷键 -->
        <section class="st-sec">
          <div class="st-label">快捷键</div>
          <div class="st-keys">
            <div v-for="s in shortcuts" :key="s.keys" class="st-keyrow">
              <span class="st-kbd">{{ s.keys }}</span>
              <span class="st-keydesc">{{ s.desc }}</span>
            </div>
          </div>
        </section>

        <!-- 服务状态 -->
        <section class="st-sec">
          <div class="st-label">服务状态</div>
          <div class="st-row">
            <span class="st-status" :class="health.ok ? 'on' : 'off'">
              <span class="dot"></span>{{ health.text }}
            </span>
            <button type="button" class="st-refresh" :disabled="health.loading" @click="refreshHealth">
              {{ health.loading ? '检测中…' : '重新检测' }}
            </button>
          </div>
          <p class="st-hint">调用 /api/health：数据库、RAG 知识库等运行状态。</p>
        </section>

        <!-- E2 审计日志展示位（后端未接入，占位） -->
        <section class="st-sec">
          <div class="st-label">审计日志</div>
          <button type="button" class="st-audit" @click="openAudit">查看审计日志</button>
          <p class="st-hint">合规审计（谁、何时、做了什么）由后端审计服务提供，接入后在此展示。</p>
        </section>
      </div>
    </aside>

    <!-- E2 审计日志占位弹窗 -->
    <div v-if="auditOpen" class="audit-mask" @click="nav.closeAudit()">
      <div class="audit-modal" role="dialog" aria-modal="true" aria-label="审计日志" @click.stop>
        <b>审计日志</b>
        <p class="st-hint">
          后端审计服务（audit.py）尚未接入。该展示位已预留：接入后将在此按时间展示
          谁、何时、调用了什么工具、涉及哪些数据表及结果状态。
        </p>
        <div class="audit-actions">
          <button type="button" class="onb-btn" @click="nav.closeAudit()">知道了</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
