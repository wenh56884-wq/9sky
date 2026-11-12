<script setup>
import { computed, watch, onMounted, onUnmounted } from 'vue'
import { SRC_ICONS, SD_VAR, svgNode } from '../utils/sources'
import { useSourceDrawer } from '../composables/useSourceDrawer'

const drawer = useSourceDrawer()
const { state } = drawer

const payload = computed(() => state.payload)

const styleVars = computed(() => {
  if (!payload.value) return {}
  const key = SD_VAR[payload.value.kind] || 'kb'
  return {
    '--ds-c': `var(--ds-${key})`,
    '--ds-c-bg': `var(--ds-${key}-bg)`,
  }
})

function badgeHtml(d) {
  return svgNode(SRC_ICONS[d.kind] || SRC_ICONS.doc, 12) + '<span>' + d.tag + '</span>'
}

function onKey(e) {
  if (e.key === 'Escape') drawer.close()
}

onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))

// 打开时锁定背景滚动可省略（遮罩已覆盖）；关闭仅切类
watch(() => state.open, (v) => {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = v ? 'hidden' : ''
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="src-drawer-mask" :class="{ show: state.open }" @click="drawer.close()"></div>
    <aside
      class="src-drawer"
      :class="{ open: state.open }"
      :style="styleVars"
      aria-label="数据来源详情"
    >
      <template v-if="payload">
        <div class="sd-head">
          <span class="ds-badge" v-html="badgeHtml(payload)"></span>
          <div class="sd-title">
            <b>{{ payload.title }}</b>
            <small v-if="payload.sub">{{ payload.sub }}</small>
          </div>
          <button type="button" class="sd-close" title="关闭（Esc）" @click="drawer.close()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
          </button>
        </div>
        <div class="sd-body">
          <div v-if="payload.detailRows && payload.detailRows.length" class="sd-sec">
            <div class="sd-label">基本信息</div>
            <dl class="sd-kv">
              <template v-for="(pair, i) in payload.detailRows" :key="i">
                <dt v-if="pair[1]">{{ pair[0] }}</dt>
                <dd v-if="pair[1]">{{ pair[1] }}</dd>
              </template>
            </dl>
          </div>

          <div v-if="payload.tables && payload.tables.length" class="sd-sec">
            <div class="sd-label">涉及数据表</div>
            <div class="sd-chips">
              <span v-for="t in payload.tables" :key="t" class="sd-chip">{{ t }}</span>
            </div>
          </div>

          <div v-if="payload.pills && payload.pills.length" class="sd-sec">
            <div class="sd-label">定位</div>
            <div class="sd-chips">
              <span v-for="p in payload.pills" :key="p" class="ds-pill">{{ p }}</span>
            </div>
          </div>

          <div v-if="payload.notes && payload.notes.length" class="sd-sec">
            <div class="sd-label">说明</div>
            <div class="sd-text">{{ payload.notes.filter(Boolean).join('\n') }}</div>
          </div>

          <div v-if="payload.snippet" class="sd-sec">
            <div class="sd-label">原文摘录</div>
            <div class="sd-text">{{ payload.snippet }}</div>
          </div>

          <div v-if="payload.sql" class="sd-sec">
            <div class="sd-label">执行的 SQL</div>
            <pre class="sd-sql">{{ payload.sql }}</pre>
          </div>
        </div>
      </template>
    </aside>
  </Teleport>
</template>
