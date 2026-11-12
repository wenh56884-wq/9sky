// N2 导出对话：用 Markdown 拼接对话内容（用户问题 + 助手回答），Blob 下载
// 文件名含标题与日期，如：对话-销售复盘-20261112.md

function pad(n) {
  return String(n).padStart(2, '0')
}

function dateStamp(d) {
  const date = d || new Date()
  return '' + date.getFullYear() + pad(date.getMonth() + 1) + pad(date.getDate())
}

// 文件名安全化：去掉路径非法字符，限制长度
function safeName(title) {
  return String(title || '未命名会话')
    .replace(/[\\/:*?"<>|\s]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40) || '未命名会话'
}

// 把消息数组拼成 Markdown：每对「提问/回答」一个小节
export function buildChatMarkdown(title, messages) {
  const lines = []
  lines.push('# 对话：' + (title || '未命名会话'))
  lines.push('')
  lines.push('导出时间：' + new Date().toLocaleString('zh-CN'))
  lines.push('')
  let qNo = 0
  for (const m of messages || []) {
    if (m.role === 'user') {
      qNo += 1
      lines.push('## 提问 ' + qNo)
      lines.push('')
      lines.push(String(m.content || '').replace(/\r\n/g, '\n'))
      lines.push('')
    } else {
      lines.push('## 回答 ' + qNo)
      lines.push('')
      lines.push(String(m.content || '（本轮没有生成回答）').replace(/\r\n/g, '\n'))
      lines.push('')
    }
  }
  return lines.join('\n')
}

export function downloadMarkdown(title, content) {
  const name = '对话-' + safeName(title) + '-' + dateStamp() + '.md'
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return name
}

// 一键导出：拼 Markdown 并触发下载，返回文件名
export function exportChat(title, messages) {
  const md = buildChatMarkdown(title, messages)
  return downloadMarkdown(title, md)
}
