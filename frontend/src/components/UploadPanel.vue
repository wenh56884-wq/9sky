<script setup>
import { ref } from 'vue'
import { useUploads } from '../composables/useUploads'

const {
  state, closePanel, setToken, uploadFiles, deleteUpload, openDataPreview, fmtSize,
} = useUploads()

const fileInput = ref(null)
const over = ref(false)

const KIND = { table: '表格', document: '文档', image: '图片' }

function onPick(e) {
  uploadFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  over.value = false
  uploadFiles(e.dataTransfer && e.dataTransfer.files)
}
</script>

<template>
  <div class="up-mask" :class="{ show: state.panelOpen }" @click="closePanel"></div>
  <aside class="up-panel" :class="{ open: state.panelOpen }" aria-label="数据文件管理">
    <div class="up-head">
      <b>资料上传</b>
      <button class="up-close" type="button" title="关闭" @click="closePanel">×</button>
    </div>
    <div class="up-body">
      <div
        class="up-drop"
        :class="{ over }"
        @click="fileInput && fileInput.click()"
        @dragover.prevent="over = true"
        @dragleave.prevent="over = false"
        @drop.prevent="onDrop"
      >
        <input
          ref="fileInput"
          type="file"
          multiple
          hidden
          accept=".xlsx,.xlsm,.xls,.ods,.csv,.tsv,.txt,.json,.jsonl,.ndjson,.parquet,.pq,.feather,.sqlite,.sqlite3,.db,.xml,.pdf,.docx,.pptx,.md,.markdown,.png,.jpg,.jpeg,.bmp,.webp,.tif,.tiff"
          @change="onPick"
        />
        <div class="up-drop-in">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
          <span>点击或拖入表格、文档、图片</span>
          <small>表格入 SQLite；PDF、Word、PPT 和图片文字自动提取，直接问 AI</small>
        </div>
      </div>

      <div class="up-token">
        <input
          :value="state.token"
          type="password"
          placeholder="管理员令牌（后端未设置 ADMIN_TOKEN 时留空）"
          autocomplete="off"
          @input="setToken($event.target.value)"
        />
      </div>

      <div class="up-list">
        <div v-if="state.loading" class="up-empty">正在加载…</div>
        <template v-else>
          <div v-if="!state.files.length" class="up-empty">还没有上传文件。上传后会自动解析并记住表结构。</div>
          <div v-for="f in state.files" :key="f.name" class="up-item">
            <div class="up-meta">
              <div class="up-name">{{ f.name }}</div>
              <div class="up-sub">
                {{ KIND[f.kind] || '文件' }} · {{ fmtSize(f.size) }} · {{ f.uploaded_at || '' }}
                <span v-if="f.status"> · {{ f.status }}</span>
                <span v-if="!f.supported"> · 格式不支持</span>
              </div>
            </div>
            <div class="up-actions">
              <button v-if="f.supported" class="up-view" type="button" @click="openDataPreview(f)">查看</button>
              <button class="up-del" type="button" @click="deleteUpload(f.name)">删除</button>
            </div>
          </div>
        </template>
      </div>

      <div class="up-mem">
        自动记忆：已学 {{ state.memory.tables || 0 }} 个文件的表结构，沉淀 {{ state.memory.experiences || 0 }} 次查询经验
      </div>
    </div>
  </aside>
</template>
