<script setup>
// 审批中心抽屉（管理员/超管可见）：工具审批 / 数据变更 / 变更历史
// 契约 §4.3：GET /api/approvals 列表；POST /api/approvals/<id> 决策（approve/reject/edit）
// 契约 §8.5：GET /api/writes/pending、POST /api/writes/<proposal_id>/decide、GET /api/writes/history
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { request } from '../api'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useNav } from '../composables/useNav'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'
import WriteProposalCard from './WriteProposalCard.vue'

const auth = useAuthStore()
const nav = useNav()
const { toast } = useToast()
const { confirm } = useConfirm()

const tab = ref('tools') // tools | writes | history
const open = computed(() => nav.state.approvalCenterOpen)

// ---- 工具审批（现有功能，保持不变）----
const items = ref([])
const loading = ref(false)
const error = ref('')
const busyId = ref('')

// 编辑参数（edit 决策）
const editingId = ref('')
const editArgs = ref('')
const editError = ref('')

function operatorId(it) {
  const op = it.operator_id || (it.operator && typeof it.operator === 'object' ? (it.operator.id || '') : '')
  return String(op || '')
}

function operatorName(it) {
  const op = it.operator_id || (it.operator && typeof it.operator === 'object' ? it.operator.username : '')
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

// ---- 数据变更（§8.5）----
const writes = ref([])
const writesLoading = ref(false)
const writesError = ref('')
const writeStatus = ref({}) // proposal_id -> 卡片状态（卡片操作后回传）

async function loadWrites() {
  writesLoading.value = true
  writesError.value = ''
  try {
    const data = await request('/api/writes/pending')
    writes.value = data.items || []
  } catch (e) {
    writesError.value = e.message
  } finally {
    writesLoading.value = false
  }
}

// 操作者显示名：管理员可拉用户列表解析 id → 姓名；普通用户直接显示 id
const userNames = ref({})
async function loadUserNames() {
  if (!auth.isAdmin) return
  try {
    const users = await auth.listUsers()
    const map = {}
    for (const u of users) map[u.id] = u.username
    userNames.value = map
  } catch (_) {
    // 解析失败则退回显示 operator_id
  }
}
function operatorLabel(id) {
  return userNames.value[id] || (id || '—')
}

function opLabel(op) {
  const o = String(op || '').toUpperCase()
  if (o === 'INSERT') return '新增'
  if (o === 'UPDATE') return '修改'
  if (o === 'DELETE') return '删除'
  return op || '变更'
}

// 卡片状态回传：非待审批后刷新列表（该项已从待审列表消失）
function onCardChanged(id, e) {
  writeStatus.value = { ...writeStatus.value, [id]: e.status }
  if (e.status !== 'pending') loadWrites()
}

// 审批操作（§8.5：POST /api/writes/<proposal_id>/decide）
async function decideWrite(item, decision) {
  if (!item) return
  // 客户端预检：角色不足直接提示（后端仍会按 required_role 鉴权，403 是最终防线）
  if (decision === 'approve' && Number(item.required_role) > auth.role) {
    toast.error(`需${ROLE_LABELS[item.required_role] || '高角色'}批准，当前账号无权批准。`)
    return
  }
  if (decision === 'reject') {
    const p = item.payload || {}
    const ok = await confirm({
      title: '驳回变更草案',
      text: `确定驳回 ${p.database}.${p.table} 的${opLabel(p.operation)}操作吗？驳回后数据不会被改动。`,
      okText: '确认驳回',
      danger: true,
    })
    if (!ok) return
  }
  try {
    await request('/api/writes/' + encodeURIComponent(item.id) + '/decide', {
      method: 'POST',
      body: JSON.stringify({ decision, message: decision === 'reject' ? '已驳回' : '' }),
    })
    toast.success(decision === 'approve' ? '已批准，变更已执行' : '已驳回，数据未改动')
    await loadWrites()
    selectedWrite.value = 0
  } catch (e) {
    toast.error('操作失败：' + e.message)
  }
}

// ---- 变更历史（§8.5：GET /api/writes/history，role ≥ 2）----
const history = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const historyFilter = ref('')

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    const q = historyFilter.value ? '?status=' + encodeURIComponent(historyFilter.value) : ''
    const data = await request('/api/writes/history' + q)
    history.value = data.items || []
  } catch (e) {
    historyError.value = e.message
  } finally {
    historyLoading.value = false
  }
}

const HISTORY_STATUS = {
  applied: '已执行',
  reverted: '已撤销',
  failed: '失败',
  rejected: '已驳回',
  approved: '已批准',
  pending: '待审批',
}
function historyStatusText(v) {
  return HISTORY_STATUS[v] || v || '—'
}

async function revertChange(row) {
  const ok = await confirm({
    title: '撤销变更',
    text: `确定撤销 ${row.db_name}.${row.table_name} 的${opLabel(row.operation)}操作吗？数据将恢复到变更前。`,
    okText: '确认撤销',
    danger: true,
  })
  if (!ok) return
  try {
    const data = await request('/api/writes/' + encodeURIComponent(row.id) + '/revert', {
      method: 'POST',
      body: '{}',
    })
    toast.success(data.message || '已撤销')
    await loadHistory()
  } catch (e) {
    toast.error('撤销失败：' + e.message)
  }
}

// ---- tab 切换与加载 ----
function switchTab(t) {
  tab.value = t
}

watch(open, (v) => {
  if (!v) return
  load()
  if (tab.value === 'writes') loadWrites()
  else if (tab.value === 'history') loadHistory()
})

watch(tab, (t) => {
  if (!open.value) return
  if (t === 'writes') loadWrites()
  else if (t === 'history') loadHistory()
  else load()
})

// 管理员登录后在挂载时也拉一次工具审批，用于侧栏徽标
if (auth.isAdmin) load()
onMounted(() => {
  loadUserNames()
})

// ---- 快捷键：J/K 上下选择、A 批准、R 驳回（仅数据变更 tab）----
const selectedWrite = ref(0)

function onKeydown(e) {
  if (!open.value || tab.value !== 'writes') return
  const t = e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
  const key = e.key.toLowerCase()
  if (key === 'j') {
    e.preventDefault()
    if (writes.value.length) selectedWrite.value = (selectedWrite.value + 1) % writes.value.length
  } else if (key === 'k') {
    e.preventDefault()
    if (writes.value.length) selectedWrite.value = (selectedWrite.value - 1 + writes.value.length) % writes.value.length
  } else if (key === 'a') {
    e.preventDefault()
    decideWrite(writes.value[selectedWrite.value], 'approve')
  } else if (key === 'r') {
    e.preventDefault()
    decideWrite(writes.value[selectedWrite.value], 'reject')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="ap-mask" :class="{ show: open }" @click="close"></div>
  <aside class="ap-panel" :class="{ open }">
    <header class="ap-head-bar">
      <b>审批中心</b>
      <div class="ap-head-right">
        <span v-if="tab === 'tools' && items.length" class="ap-pending-count">{{ items.length }} 项待审批</span>
        <span v-else-if="tab === 'writes' && writes.length" class="ap-pending-count">{{ writes.length }} 项待审批</span>
        <button type="button" class="up-close" @click="close">×</button>
      </div>
    </header>

    <div class="ap-tabs">
      <button type="button" :class="{ active: tab === 'tools' }" @click="switchTab('tools')">工具审批</button>
      <button type="button" :class="{ active: tab === 'writes' }" @click="switchTab('writes')">数据变更</button>
      <button type="button" :class="{ active: tab === 'history' }" @click="switchTab('history')">变更历史</button>
    </div>

    <div class="ap-body">
      <!-- 工具审批：现有功能 -->
      <template v-if="tab === 'tools'">
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
      </template>

      <!-- 数据变更：待审批写草案 -->
      <template v-else-if="tab === 'writes'">
        <div v-if="writesError" class="ap-error">{{ writesError }}</div>
        <div v-if="writesLoading" class="ap-empty">加载中…</div>
        <div v-else-if="!writes.length" class="ap-empty">暂无待你审批的数据变更。</div>

        <article
          v-for="(it, idx) in writes"
          :key="it.id"
          class="ap-item wp-list-item"
          :class="{ selected: idx === selectedWrite }"
          @click="selectedWrite = idx"
        >
          <p class="ap-meta">
            {{ operatorLabel(it.operator_id) }} · {{ fmtTime(it.created_at) }} ·
            {{ it.payload.database }}.{{ it.payload.table }} · {{ opLabel(it.payload.operation) }} ·
            影响 {{ it.payload.estimated_rows }} 行 · 风险 {{ it.payload.risk }}
            <template v-if="Number(it.required_role) > auth.role"> · 需{{ ROLE_LABELS[it.required_role] }}批准</template>
          </p>
          <WriteProposalCard
            :proposal="it.payload"
            :status="writeStatus[it.id] || 'pending'"
            @changed="(e) => onCardChanged(it.id, e)"
          />
        </article>
      </template>

      <!-- 变更历史 -->
      <template v-else>
        <div class="ap-history-bar">
          <label>状态筛选
            <select v-model="historyFilter" @change="loadHistory">
              <option value="">全部</option>
              <option value="applied">已执行</option>
              <option value="reverted">已撤销</option>
              <option value="failed">失败</option>
              <option value="rejected">已驳回</option>
            </select>
          </label>
        </div>
        <div v-if="historyError" class="ap-error">{{ historyError }}</div>
        <div v-if="historyLoading" class="ap-empty">加载中…</div>
        <div v-else-if="!history.length" class="ap-empty">暂无变更记录。</div>

        <div v-else class="ap-history">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>操作者</th>
                <th>库.表</th>
                <th>操作</th>
                <th>影响行数</th>
                <th>状态</th>
                <th>审批人</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in history" :key="row.id">
                <td>{{ fmtTime(row.applied_at || row.reverted_at) }}</td>
                <td class="wrap">{{ row.actor_name || row.actor_id || '—' }}</td>
                <td class="wrap">{{ row.db_name }}.{{ row.table_name }}</td>
                <td>{{ opLabel(row.operation) }}</td>
                <td>{{ row.affected_rows != null ? row.affected_rows : '—' }}</td>
                <td :class="'st-' + row.status">{{ historyStatusText(row.status) }}</td>
                <td class="wrap">{{ row.approver_name || row.approver_id || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </aside>
</template>
