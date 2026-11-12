<script setup>
import { ref, computed } from 'vue'
import {
  SRC_ICONS, SRC_TAGS, svgNode,
  buildSourceItem, buildDeepItem,
} from '../utils/sources'
import { useSourceDrawer } from '../composables/useSourceDrawer'

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const drawer = useSourceDrawer()

// 把原始来源项转成展示 + 抽屉 payload
const display = computed(() =>
  (props.items || [])
    .filter(Boolean)
    .map((it) => (it.source ? buildDeepItem(it) : buildSourceItem(it)))
)

const folded = ref(props.items.length > 6)

function badgeHtml(d) {
  return svgNode(SRC_ICONS[d.kind] || SRC_ICONS.doc, 12) + '<span>' + d.tag + '</span>'
}

function rowPill(d) {
  if (d.rows == null) return ''
  const n = Number(d.rows)
  return (isNaN(n) ? d.rows : n.toLocaleString('zh-CN')) + ' 行数据'
}

function openDrawer(d) {
  drawer.open(d)
}
</script>

<template>
  <div v-if="display.length" class="data-src" :class="{ folded }">
    <button type="button" class="ds-head" title="点击展开 / 收起数据来源" @click="folded = !folded">
      <span class="ds-head-icon" v-html="svgNode(SRC_ICONS.database, 14)"></span>
      <span>数据来源</span>
      <span class="ds-count">{{ display.length }} 处</span>
      <span class="ds-caret">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
      </span>
    </button>
    <div class="ds-list">
      <div
        v-for="(d, i) in display"
        :key="i"
        class="ds-item"
        :class="'k-' + d.kind"
        title="点击查看来源详情"
        @click="openDrawer(d)"
      >
        <span class="ds-badge" v-html="badgeHtml(d)"></span>
        <div class="ds-main">
          <div class="ds-name">{{ d.title }}</div>
          <div v-if="d.sub" class="ds-sub">{{ d.sub }}</div>
        </div>
        <div class="ds-body">
          <span v-for="t in d.tables" :key="t" class="ds-chip">{{ t }}</span>
          <span v-if="rowPill(d)" class="ds-pill">{{ rowPill(d) }}</span>
          <span v-for="(n, j) in d.notes" :key="j" class="ds-note">{{ n }}</span>
        </div>
        <details v-if="d.sql" class="ds-sql" @click.stop>
          <summary>查看执行的 SQL</summary>
          <pre>{{ d.sql }}</pre>
        </details>
        <span class="ds-more">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>
        </span>
      </div>
    </div>
  </div>
</template>
