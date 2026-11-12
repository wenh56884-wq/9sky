<script setup>
// 审批中心抽屉（管理员/超管可见）：待审批列表 + 审批处理
// 契约 §4.3：GET /api/approvals 列表；POST /api/approvals/<id> 决策（approve/reject/edit）
import { ref, computed } from 'vue'
import { request } from '../api'
import { useAuthStore } from '../stores/auth'
import { useNav } from '../composables/useNav'

const auth = useAuthStore()
const nav = useNav()

const items = ref([])
const loading = ref(false)
const error = ref('')
const busyId = ref('')

// 编辑参数（edit 决策）
const editingId = ref('')
const editArgs = ref('')
const editError = ref('')

const open = computed(() => nav.state.approvalCenterOpen)

function operatorId(it) {
  const op = it.operator
  return op && typeof op === 'object' ? (op.id || '') : String(op || '')
}

function operatorName(it) {
  const op = it.operator
  if (op && typeof op === 'object') return op.username || op.id || '—'
  return op || '—'
}

// 当前用户能否决策该条
function canDecide(it) {
  if (it.stage === 'awaiting_admin') return auth.isAdmin
  if (it.stage === 'awaiting_operator') return !!auth.user && auth.user.id === operatorId(it)
  return false
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request('/api/approvals')
    items.value = data.items || []
    nav.setApprovalPending(items.value.length)
  } catch (e) {
    error.value = e.message
    nav.setApprovalPending(0)
  } finally {
    loading.value = false
  }
}

// 打开时加载；管理员登录后在挂载时也拉一次，用于侧栏徽标
if (auth.isAdmin) load()

function close() {
  nav.closeApprovalCenter()
}

async function decide(it, decision, args) {
  if (busyId.value) return
  busyId.value = it.id
  error.value = ''
  try {
    const body = { decision }
    if (args !== undefined) body.args = args
    await request('/api/approvals/' + encodeURIComponent(it.id), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (decision === 'edit') {
      editingId.value = ''
      editArgs.value = ''
      editError.value = ''
    }
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busyId.value = ''
  }
}

function startEdit(it) {
  editingId.value = it.id
  editError.value = ''
  editArgs.value = JSON.stringify(it.args || {}, null, 2)
}

function submitEdit(it) {
  let args
  try {
    args = JSON.parse(editArgs.value)
  } catch (_) {
    editError.value = '参数不是合法 JSON，无法提交。'
    return
  }
  decide(it, 'edit', args)
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 19)
}

function riskText(it) {
  return it.risk_level === 'high' ? '高风险' : '低风险'
}

function stageText(it) {
  if (it.stage === 'awaiting_admin') return '待管理员审批'
  if (it.stage === 'awaiting_operator') return '等待操作者确认'
  return '已处理'
}
</script>

<template>
  <div class="ap-mask" :class="{ show: open }" @click="close"></div>
  <aside class="ap-panel" :class="{ open }">
    <header class="ap-head-bar">
      <b>审批中心</b>
      <div class="ap-head-right">
        <span v-if="items.length" class="ap-pending-count">{{ items.length }} 项待审批</span>
        <button type="button" class="up-close" @click="close">×</button>
      </div>
    </header>

    <div class="ap-body">
      <div v-if="error" class="ap-error">{{ error }}</div>
      <div v-if="loading" class="ap-empty">加载中…</div>
      <div v-else-if="!items.length" class="ap-empty">暂无待审批事项。</div>

      <article v-for="it in items" :key="it.id" class="ap-item" :class="{ high: it.risk_level === 'high' }">
        <div class="ap-item-head">
          <span class="ap-risk-tag" :class="it.risk_level === 'high' ? 'high' : 'low'">{{ riskText(it) }}</span>
          <span class="ap-stage-tag" :class="it.risk_level === 'high' ? 'high' : 'low'">{{ stageText(it) }}</span>
          <span class="ap-tool">{{ it.tool }}</span>
        </div>
        <p class="ap-desc">{{ it.description }}</p>
        <p class="ap-meta">
          操作者：{{ operatorName(it) }} · 会话 {{ it.thread_id || '—' }} · {{ fmtTime(it.created_at) }}
        </p>

        <template v-if="!canDecide(it)">
          <p class="ap-waiting">
            {{ it.risk_level === 'high' && it.stage === 'awaiting_admin' ? '需管理员审批，当前账号无法操作。' : '等待操作者本人确认。' }}
          </p>
        </template>

        <template v-else>
          <div v-if="editingId === it.id" class="ap-edit">
            <textarea v-model="editArgs" rows="4" aria-label="修改参数（JSON）"></textarea>
            <div v-if="editError" class="ap-edit-error">{{ editError }}</div>
          </div>
          <div class="ap-actions">
            <button
              type="button"
              class="ap-approve"
              :disabled="busyId === it.id"
              @click="decide(it, 'approve')"
            >批准</button>
            <button
              type="button"
              class="ap-reject"
              :disabled="busyId === it.id"
              @click="decide(it, 'reject')"
            >拒绝</button>
            <button
              type="button"
              class="ap-edit-btn"
              :disabled="busyId === it.id"
              @click="editingId === it.id ? submitEdit(it) : startEdit(it)"
            >{{ editingId === it.id ? '确认编辑' : '编辑参数' }}</button>
          </div>
        </template>
      </article>
    </div>
  </aside>
</template>
