<script setup>
import { ref, computed } from 'vue'
import { request } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  approval: { type: Object, required: true },
})

const auth = useAuthStore()

const resolved = ref(false)
const result = ref('')
const busy = ref(false)

// 编辑参数（decision=edit）：展开 JSON 文本域
const editing = ref(false)
const editArgs = ref('')
const editError = ref('')

const riskLevel = computed(() => (props.approval.risk_level === 'high' ? 'high' : 'low'))
const riskText = computed(() => (riskLevel.value === 'high' ? '高风险' : '低风险'))

const stageText = computed(() => {
  const stage = props.approval.stage
  if (stage === 'awaiting_admin') return '待管理员审批'
  if (stage === 'awaiting_operator') return '等待操作者确认'
  if (stage === 'done') return '已处理'
  return '等待确认'
})

// 当前用户能否决策：低风险操作者本人自批；高风险需管理员/超管
const canDecide = computed(() => {
  if (props.approval.stage === 'awaiting_admin') return auth.isAdmin
  if (props.approval.stage === 'awaiting_operator') return true // 会话由当前用户触发，其本人即操作者
  return false
})

const allowed = computed(() => {
  const list = Array.isArray(props.approval.allowed_decisions) ? props.approval.allowed_decisions : ['approve', 'reject']
  return list
})

function canDo(decision) {
  return !resolved.value && !busy.value && canDecide.value && allowed.value.includes(decision)
}

async function decide(decision, args) {
  if (busy.value || resolved.value) return
  busy.value = true
  result.value = ''
  try {
    const body = { decision }
    if (args !== undefined) body.args = args
    await request('/api/approvals/' + encodeURIComponent(props.approval.approval_id), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    resolved.value = true
    if (decision === 'approve') result.value = '已批准，Agent 正在继续执行'
    else if (decision === 'reject') result.value = '已拒绝，Agent 将继续处理'
    else result.value = '已提交修改后的参数，Agent 将按新参数继续执行'
  } catch (error) {
    result.value = '审批提交失败：' + error.message
  } finally {
    busy.value = false
  }
}

function startEdit() {
  editing.value = true
  editError.value = ''
  editArgs.value = JSON.stringify(props.approval.args || {}, null, 2)
}

function submitEdit() {
  let args
  try {
    args = JSON.parse(editArgs.value)
  } catch (_) {
    editError.value = '参数不是合法 JSON，无法提交。'
    return
  }
  decide('edit', args)
}

const argsText = () => (props.approval.tool || 'tool') + '(' + JSON.stringify(props.approval.args || {}, null, 2) + ')'
</script>

<template>
  <section class="approval-card" :class="riskLevel">
    <div class="ap-head">
      <b>需要人工确认</b>
      <span class="ap-risk-tag" :class="riskLevel">{{ riskText }}</span>
      <span class="ap-stage-tag" :class="riskLevel">{{ stageText }}</span>
    </div>
    <div>{{ approval.description || '此操作需要批准后才能执行。' }}</div>

    <template v-if="!resolved">
      <code v-if="!editing">{{ argsText() }}</code>
      <div v-if="editing" class="ap-edit">
        <textarea
          v-model="editArgs"
          rows="5"
          aria-label="修改参数（JSON）"
        ></textarea>
        <div v-if="editError" class="ap-edit-error">{{ editError }}</div>
      </div>

      <div v-if="!canDecide" class="ap-waiting" :class="riskLevel">
        <template v-if="riskLevel === 'high' && approval.stage === 'awaiting_admin'">
          高风险操作，需管理员审批，当前账号无法决策。
        </template>
        <template v-else>等待操作者本人确认。</template>
      </div>

      <div class="ap-actions">
        <button
          v-if="canDo('approve')"
          type="button"
          class="approve"
          :disabled="busy"
          @click="decide('approve')"
        >批准执行</button>
        <button
          v-if="canDo('reject')"
          type="button"
          :disabled="busy"
          @click="decide('reject')"
        >拒绝</button>
        <button
          v-if="canDo('edit')"
          type="button"
          class="edit"
          :disabled="busy"
          @click="editing ? submitEdit() : startEdit()"
        >{{ editing ? '确认编辑' : '编辑参数' }}</button>
      </div>
    </template>

    <div v-if="result" class="approval-result">{{ result }}</div>
    <div v-else-if="resolved" class="approval-result">已处理完毕。</div>
  </section>
</template>
