<script setup>
// 写数据变更卡（契约 §8.8）：展示变更草案，支持批准执行 / 驳回 / 修改后重提
// 状态机（§8.10）：pending → approved → applied | failed；pending → rejected；applied → reverted
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { request } from '../api'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useToast } from '../composables/useToast'
import { useConfirm } from '../composables/useConfirm'

const props = defineProps({
  proposal: { type: Object, required: true }, // {proposal_id, database, table, operation, sql, risk, required_role, estimated_rows, preview, expires_at, reason, ...}
  status: { type: String, default: 'pending' }, // pending/approved/rejected/applied/failed/reverted
  execution: { type: Object, default: null },   // 执行结果 {ok, affected_rows, status, error_id, message}
})

const emit = defineEmits(['changed'])

const auth = useAuthStore()
const { toast } = useToast()
const { confirm } = useConfirm()

// ---- 状态：本地持有，外部（聊天流事件）通过 prop 同步 ----
const status = ref(props.status || 'pending')
const busy = ref(false)
const localExecution = ref(props.execution || null)

watch(() => props.status, (v) => { if (v) status.value = v })
watch(() => props.execution, (v) => { if (v) localExecution.value = v })

function syncOut() {
  emit('changed', { status: status.value, execution: localExecution.value })
}

// ---- 头部标签 ----
const opText = computed(() => {
  const op = String(props.proposal.operation || '').toUpperCase()
  if (op === 'INSERT') return '新增'
  if (op === 'UPDATE') return '修改'
  if (op === 'DELETE') return '删除'
  return props.proposal.operation || '变更'
})
const opClass = computed(() => {
  const op = String(props.proposal.operation || '').toUpperCase()
  if (op === 'INSERT') return 'ins'
  if (op === 'UPDATE') return 'upd'
  if (op === 'DELETE') return 'del'
  return ''
})
const riskLevel = computed(() => {
  const r = String(props.proposal.risk || 'L1').toUpperCase()
  return ['L1', 'L2', 'L3'].includes(r) ? r : 'L1'
})

// ---- 角色门槛（§8.9）：角色 < required_role 时禁用批准 ----
const requiredRole = computed(() => Number(props.proposal.required_role) || 1)
const needApproveHint = computed(() => status.value === 'pending' && auth.role < requiredRole.value)
const approveHint = computed(() =>
  needApproveHint.value ? `需${ROLE_LABELS[requiredRole.value] || '高角色'}批准` : ''
)
const canApprove = computed(() =>
  status.value === 'pending' && !busy.value && auth.role >= requiredRole.value
)

// ---- 待审批倒计时（§8.5 超时自动拒绝）----
const now = ref(Date.now())
let timer = null
const expiresAt = computed(() => {
  const v = props.proposal.expires_at
  if (!v) return null
  const t = new Date(v).getTime()
  return t > 0 ? t : null
})
const countdown = computed(() => {
  if (status.value !== 'pending' || !expiresAt.value) return ''
  const left = expiresAt.value - now.value
  if (left <= 0) return '已过期'
  const total = Math.floor(left / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
})
watch([status, expiresAt], ([st, exp]) => {
  if (st === 'pending' && exp) {
    now.value = Date.now()
    if (!timer) timer = setInterval(() => { now.value = Date.now() }, 1000)
  } else if (timer) {
    clearInterval(timer)
    timer = null
  }
}, { immediate: true })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })

// ---- 差异表（§8.8：Before/After 双列，被改单元格高亮）----
const preview = computed(() => props.proposal.preview || {})
const columns = computed(() => preview.value.columns || [])
const beforeRows = computed(() => preview.value.before || [])
const afterRows = computed(() => preview.value.after || [])
const sampleLimit = computed(() => Number(preview.value.sample_limit) || 20)
const totalRows = computed(() => Math.max(beforeRows.value.length, afterRows.value.length))
const truncated = computed(() => totalRows.value > sampleLimit.value)
const displayRows = computed(() => Math.min(totalRows.value, sampleLimit.value))

function cellText(v) {
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}
function isChanged(b, a) {
  return String(b ?? '') !== String(a ?? '')
}
function rowCells(i) {
  const b = beforeRows.value[i]
  const a = afterRows.value[i]
  return columns.value.map((_, j) => {
    const bv = b ? b[j] : null
    const av = a ? a[j] : null
    return { b: cellText(bv), a: cellText(av), changed: isChanged(bv, av) }
  })
}

// ---- 状态文案 ----
const statusText = computed(() => {
  switch (status.value) {
    case 'pending': return '等待审批'
    case 'approved': return '已批准'
    case 'rejected': return '已驳回'
    case 'applied': return '已执行'
    case 'failed': return '执行失败'
    case 'reverted': return '已撤销'
    default: return status.value
  }
})
const statusDetail = computed(() => {
  switch (status.value) {
    case 'pending': return countdown.value ? `剩余 ${countdown.value}` : ''
    case 'approved': return '等待执行'
    case 'rejected': return props.proposal.reject_reason || '变更未获批准，已取消，未改动任何数据'
    case 'applied': {
      const exec = localExecution.value
      const rows = exec && exec.affected_rows != null ? exec.affected_rows : props.proposal.estimated_rows
      return `影响 ${rows} 行`
    }
    case 'failed': {
      const exec = localExecution.value
      const detail = exec && (exec.message || exec.error_id)
      return detail ? `失败：${detail}` : '执行失败，可重新发起'
    }
    case 'reverted': return '数据已恢复到变更前'
    default: return ''
  }
})

// ---- 操作（§8.5：POST /api/writes/<proposal_id>/decide）----
async function decide(decision, message = '') {
  if (busy.value || status.value !== 'pending') return
  busy.value = true
  try {
    const data = await request('/api/writes/' + encodeURIComponent(props.proposal.proposal_id) + '/decide', {
      method: 'POST',
      body: JSON.stringify({ decision, message }),
    })
    if (decision === 'approve') {
      const exec = data.execution || null
      localExecution.value = exec
      if (exec && exec.ok === false) {
        status.value = 'failed'
        toast.error('执行失败：' + (exec.message || exec.error_id || '未知错误'))
      } else {
        status.value = 'applied'
        const rows = exec && exec.affected_rows != null ? exec.affected_rows : props.proposal.estimated_rows
        toast.success(`已批准执行，影响 ${rows} 行`)
      }
    } else {
      status.value = 'rejected'
      toast.info('已驳回，数据未改动')
    }
    syncOut()
  } catch (error) {
    toast.error('操作失败：' + error.message)
  } finally {
    busy.value = false
  }
}

async function reject() {
  const ok = await confirm({
    title: '驳回变更草案',
    text: `确定驳回对 ${props.proposal.database}.${props.proposal.table} 的${opText.value}操作吗？驳回后数据不会被改动。`,
    okText: '确认驳回',
    danger: true,
  })
  if (ok) decide('reject')
}

// 后端没有"编辑草案"接口：复制 SQL，引导用户在对话里修改后重新发起（生成新草案）
async function rePropose() {
  const sql = props.proposal.sql || ''
  try {
    await navigator.clipboard.writeText(sql)
    toast.info('已复制 SQL。修改后在对话里重新发起，即可生成新草案。')
  } catch (_) {
    toast.info('请手动复制下方 SQL，修改后重新发起即可。')
  }
}

const rowsDisplay = computed(() =>
  props.proposal.estimated_rows != null ? props.proposal.estimated_rows : '—'
)
</script>

<template>
  <section class="wp-card" :class="['st-' + status, opClass]">
    <header class="wp-head">
      <span class="wp-table">{{ proposal.database }}.{{ proposal.table }}</span>
      <span class="wp-op" :class="opClass">{{ opText }}</span>
      <span class="wp-risk" :class="'r-' + riskLevel" :title="'风险等级 ' + riskLevel">{{ riskLevel }}</span>
      <span class="wp-status" :class="'s-' + status">
        {{ statusText }}<template v-if="statusDetail"> · {{ statusDetail }}</template>
      </span>
    </header>

    <div class="wp-body">
      <div class="wp-rows">
        <span class="wp-rows-num">{{ rowsDisplay }}</span>
        <span class="wp-rows-label">行预计影响</span>
      </div>
      <p v-if="proposal.reason" class="wp-reason">原因：{{ proposal.reason }}</p>

      <details class="wp-sql">
        <summary>查看 SQL</summary>
        <pre><code>{{ proposal.sql }}</code></pre>
      </details>

      <div v-if="columns.length" class="wp-diff">
        <div class="wp-diff-head">
          <span class="wp-diff-col">变更前</span>
          <span class="wp-diff-col">变更后</span>
        </div>
        <div v-for="i in displayRows" :key="i" class="wp-diff-row">
          <template v-for="(cell, j) in rowCells(i - 1)" :key="j">
            <div class="wp-diff-cell before" :class="{ changed: cell.changed }">{{ cell.b }}</div>
            <div class="wp-diff-cell after" :class="{ changed: cell.changed }">{{ cell.a }}</div>
          </template>
        </div>
        <p v-if="truncated" class="wp-diff-note">仅显示前 {{ sampleLimit }} 行（共 {{ totalRows }} 行）</p>
      </div>
      <p v-else class="wp-diff-empty">暂无预览数据。</p>
    </div>

    <footer v-if="status === 'pending'" class="wp-actions">
      <button type="button" class="reject" :disabled="busy" @click="reject">驳回</button>
      <button type="button" class="repropose" :disabled="busy" @click="rePropose">修改后重提</button>
      <button
        type="button"
        class="approve"
        :disabled="!canApprove"
        :title="needApproveHint ? approveHint : '批准执行'"
        @click="decide('approve')"
      >{{ needApproveHint ? approveHint : '批准执行' }}</button>
    </footer>
  </section>
</template>
