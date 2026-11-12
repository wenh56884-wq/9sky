// 流式问答编排：streamChat / streamDeep，事件处理 + 错误友好化
// 整合进 chat store 的 sendQuestion：直接改写传入的 assistant 消息对象
import { streamNdjson } from '../api'

// ---- 普通问答事件处理 ----

function applyStep(plan, step) {
  if (!step) return
  const key = String(step.id)
  let row = plan.steps.find((s) => String(s.id) === key)
  if (!row) {
    row = { id: step.id, title: step.title || '', status: step.status || 'pending', note: step.note || '' }
    plan.steps.push(row)
  } else {
    if (step.status) row.status = step.status
    if (step.title) row.title = step.title
    if (step.note !== undefined) row.note = step.note || ''
  }
}

function rewind(message, chars) {
  const n = Number(chars) || 0
  if (!n) return
  message.content = message.content.slice(0, Math.max(0, message.content.length - n))
  if (!message.content) {
    message.started = false
    message.typing = true
    message.status = ''
  }
}

function applyChatEvent(evt, message, showProc) {
  switch (evt.type) {
    case 'thinking':
      if (!message.plan) message.plan = { goal: '', steps: [], progress: null, thinking: evt.message || '' }
      else message.plan.thinking = evt.message || ''
      break
    case 'plan':
      message.plan = {
        goal: evt.goal || '',
        steps: (evt.steps || []).map((s) => ({ id: s.id, title: s.title || '', status: s.status || 'pending', note: s.note || '' })),
        progress: evt.progress || null,
        thinking: '',
      }
      break
    case 'plan_step':
      if (message.plan) applyStep(message.plan, evt.step)
      break
    case 'tool':
      // 仅在尚未开始出字时显示人话进度
      if (!message.started) {
        const human = evt.label || '正在使用 ' + evt.name
        message.status = human
        if (showProc) message.content = human + '…\n'
      }
      break
    case 'approval_required':
      message.status = '等待人工确认…'
      message.approvals.push({
        approval_id: evt.approval_id,
        description: evt.description || '此操作需要批准后才能执行。',
        tool: evt.tool || 'tool',
        args: evt.args || {},
        // 风险分级双级审批字段（契约 §4.4）
        risk_level: evt.risk_level || 'low',
        stage: evt.stage || 'awaiting_operator',
        allowed_decisions: evt.allowed_decisions || ['approve', 'reject'],
        resolved: false,
      })
      break
    case 'rewind':
      rewind(message, evt.chars)
      break
    case 'token':
      if (message.status) message.status = ''
      message.content += evt.content
      message.started = true
      message.typing = false
      break
    case 'sources':
      message.sources = evt.items || []
      break
    default:
      break
  }
}

export async function streamChat({ question, threadId, skill, model, controller, message, showProc }) {
  let final
  try {
    final = await streamNdjson(
      '/api/chat',
      { question, thread_id: threadId, skill: skill || '', model: model || '' },
      (evt) => applyChatEvent(evt, message, showProc),
      controller.signal
    )
  } catch (error) {
    const aborted = error.name === 'AbortError'
    if (message.started) {
      message.content += aborted
        ? '\n\n> ✋ 已经停下了，想继续或换个问法都行。'
        : `\n\n> ⚠️ **连接中断了**：${error.message}\n>\n> 确认服务在运行后，再发一次就好。`
    } else {
      message.content = aborted
        ? '已经停下了，想继续或换个问法都行。'
        : `> ⚠️ **没能连上或中途断了**：${error.message}\n>\n> 确认服务在运行、网络通畅后再试一次。`
    }
    message.typing = false
    return undefined
  }

  // 收尾：处理最终事件
  if (final && final.type === 'error') {
    const detail = String(final.message || '未知错误').trim()
    if (message.started) {
      message.content += `\n\n> ⚠️ **这次没跑完**：${detail}\n>\n> 可以直接再问一次；如果是刚改过配置，重启服务后就正常了。`
    } else {
      message.content = `> ⚠️ **这次没跑通**：${detail}\n>\n> 先确认服务在运行、网络通畅，然后重试即可。`
    }
  } else if (!message.started) {
    message.content = (final && final.answer) || '我这次没组织出回答，换个问法或再说一次试试？'
  }
  message.typing = false
  if (final && final.sources) message.sources = final.sources
  return final
}

// ---- 深度搜索事件处理 ----

function applyDeepEvent(evt, message) {
  if (!message.trace) {
    message.trace = { info: '', plan: [], search: [], gap: [], rerank: '', fail: '', sources: [] }
  }
  const t = message.trace
  switch (evt.type) {
    case 'info':
      t.info = '知识库状态：' + (evt.message || '') + ' · 引擎：' + (evt.backend || '')
      break
    case 'plan':
      t.plan = evt.queries || []
      break
    case 'search':
      t.search.push({ query: evt.query || '', hits: evt.hits ?? 0, engines: evt.engines || '', round: evt.round || 1 })
      break
    case 'gap':
      t.gap = evt.queries || []
      break
    case 'rerank':
      t.rerank = 'LLM 相关度重排：已对 ' + (evt.count || 0) + ' 个候选片段重新排序'
      break
    case 'token':
      message.content += evt.content
      message.started = true
      message.typing = false
      break
    case 'sources':
      t.sources = evt.items || []
      break
    default:
      break
  }
}

export async function streamDeep({ question, threadId, model, controller, message }) {
  let final
  try {
    final = await streamNdjson(
      '/api/deep',
      { question, thread_id: threadId, model: model || '' },
      (evt) => applyDeepEvent(evt, message),
      controller.signal
    )
  } catch (error) {
    const aborted = error.name === 'AbortError'
    if (!message.trace) message.trace = { info: '', plan: [], search: [], gap: [], rerank: '', fail: '', sources: [] }
    message.trace.fail = aborted
      ? '已经停下了，想继续或换个问法都行'
      : '没能连上后端：' + error.message + '（确认服务在运行后重试）'
    if (message.started) {
      message.content += aborted ? '\n\n> ✋ 已经停下了。' : '\n\n> ⚠️ 连接中断。'
    }
    message.typing = false
    return undefined
  }

  if (final && final.type === 'error') {
    if (!message.trace) message.trace = { info: '', plan: [], search: [], gap: [], rerank: '', fail: '', sources: [] }
    message.trace.fail = '这次没跑完：' + (final.message || '') + '（可以直接再问一次）'
  } else if (!message.started) {
    message.content = (final && final.answer) || ''
  }
  message.typing = false
  // 参考来源：优先过程事件，否则用 done 携带的
  if (message.trace) {
    if (!message.trace.sources.length && final && final.sources) message.trace.sources = final.sources
  }
  return final
}
