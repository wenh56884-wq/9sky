<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useUploads } from '../composables/useUploads'

const { state, closeDataPreview } = useUploads()

const activeSheet = ref(0)

// 打开新预览时重置到第一个 sheet
watch(() => state.preview, (p) => {
  if (p && p.kind === 'table') activeSheet.value = 0
})

const preview = computed(() => state.preview)
const loading = computed(() => state.previewLoading && !preview.value)

const info = computed(() => {
  const p = preview.value
  if (!p) return '正在读取资料…'
  if (p.kind === 'error') return '读取失败'
  if (p.kind === 'table') {
    const sheet = (p.sheets || [])[activeSheet.value]
    if (!sheet) return p.message || '没有可显示的表格数据。'
    return `${sheet.name} · ${sheet.total_rows} 行 × ${sheet.total_cols} 列`
      + (sheet.truncated ? ` · 当前显示前 ${sheet.rows.length} 行` : '')
  }
  if (p.kind === 'document' || p.kind === 'image') {
    const isImage = p.kind === 'image'
    return (isImage ? '原图与 OCR 识别文本' : '已提取的可检索文本')
      + (p.truncated ? ' · 当前显示前 16,000 字' : '')
  }
  return p.message || '此文件类型不支持预览。'
})

function imageSrc(p) {
  return '/api/uploads/' + encodeURIComponent(p.name) + '/content'
}

function onKey(e) {
  if (e.key === 'Escape' && state.previewOpen) closeDataPreview()
}
onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="data-preview-mask" :class="{ show: state.previewOpen }" @click="closeDataPreview"></div>
  <section
    v-if="state.previewOpen"
    class="data-preview"
    role="dialog"
    aria-modal="true"
    aria-labelledby="data-preview-title"
  >
    <div class="data-preview-head">
      <b class="data-preview-title" id="data-preview-title">
        {{ (state.previewName || '数据') + ' · 数据预览' }}
      </b>
      <button class="data-preview-close" type="button" title="关闭预览" aria-label="关闭预览" @click="closeDataPreview">×</button>
    </div>

    <div class="data-preview-info">{{ info }}</div>

    <!-- 表格：多 sheet 切换 -->
    <div
      v-if="preview && preview.kind === 'table' && (preview.sheets || []).length"
      class="data-preview-tabs"
    >
      <button
        v-for="(sheet, i) in preview.sheets"
        :key="i"
        class="data-preview-tab"
        :class="{ active: i === activeSheet }"
        type="button"
        @click="activeSheet = i"
      >{{ sheet.name }}</button>
    </div>

    <div class="data-preview-content">
      <!-- 加载中 -->
      <div v-if="loading" class="data-preview-empty">正在加载预览…</div>

      <!-- 表格 -->
      <template v-else-if="preview && preview.kind === 'table'">
        <template v-for="(sheet, i) in (preview.sheets || [])" :key="i" v-show="i === activeSheet">
          <p v-if="sheet.truncated" class="data-preview-note">为保持加载速度，仅展示前 {{ sheet.rows.length }} 行。</p>
          <div class="data-table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th v-for="(col, ci) in (sheet.columns || [])" :key="ci">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in (sheet.rows || [])" :key="ri">
                  <td v-for="(col, ci) in (sheet.columns || [])" :key="ci">{{ row[ci] == null ? '' : String(row[ci]) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-if="!(preview.sheets || []).length" class="data-preview-empty">
          {{ preview.message || '暂无可预览的数据' }}
        </div>
      </template>

      <!-- 文档 / 图片 -->
      <template v-else-if="preview && (preview.kind === 'document' || preview.kind === 'image')">
        <img v-if="preview.kind === 'image'" class="data-preview-image" :src="imageSrc(preview)" :alt="preview.name" />
        <div class="data-preview-section">{{ preview.kind === 'image' ? 'OCR 识别文本' : '文本内容' }}</div>
        <pre v-if="preview.text" class="data-preview-text">{{ preview.text }}</pre>
        <div v-else class="data-preview-empty">{{ preview.message || '尚未提取到文字' }}</div>
      </template>

      <!-- 错误 / 其他 -->
      <template v-else-if="preview">
        <div class="data-preview-empty">
          {{ preview.kind === 'error' ? preview.message : '无法预览此文件' }}
        </div>
      </template>
    </div>
  </section>
</template>
