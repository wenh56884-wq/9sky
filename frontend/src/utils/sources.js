// 数据来源相关的共享常量与构造工具
// 供 SourceCard / SourceDrawer / DeepTrace 复用，避免重复实现

// 来源类型图标（24x24 stroke svg 路径）
export const SRC_ICONS = {
  database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8v-13"/><path d="M4.5 12c0 1.6 3.4 2.8 7.5 2.8s7.5-1.2 7.5-2.8"/>',
  tables: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M9 9.5v10"/>',
  knowledge: '<path d="M14 3.5H7.5a1.8 1.8 0 0 0-1.8 1.8v13.4a1.8 1.8 0 0 0 1.8 1.8h9a1.8 1.8 0 0 0 1.8-1.8V8z"/><path d="M13.8 3.5V8h4.5"/><path d="M8.6 13h6.8M8.6 16.4h4.2"/>',
  forecast: '<path d="M3.5 16.8l5.2-5.2 3.4 3.4 6.4-6.4"/><path d="M13.5 8.6h5.6v5.6"/>',
  chart: '<path d="M3.5 20h17"/><rect x="5.6" y="11" width="3" height="6.4" rx=".8"/><rect x="10.8" y="7" width="3" height="10.4" rx=".8"/><rect x="16" y="13.6" width="3" height="3.8" rx=".8"/>',
  doc: '<path d="M4.5 4.5h15v15h-15z"/><path d="M7.8 9h8.4M7.8 12.4h8.4M7.8 15.8h5"/>',
}

// 来源类型 → 中文标签
export const SRC_TAGS = {
  database: '数据库',
  tables: '表格库',
  knowledge: '知识库',
  forecast: '预测',
  chart: '图表',
}

// 数据库 key → 友好名
export const DB_FRIENDLY = {
  financial_asset_management: '金融业务库',
  healthcare_analytics_competition: '医疗业务库',
  telecom_operations_db: '通信业务库',
}

// 来源类型 → 主题变量后缀（database→db …），doc 类引用沿用知识库紫色
export const SD_VAR = { database: 'db', tables: 'tab', knowledge: 'kb', forecast: 'ml', chart: 'chart' }

// 生成一个内联 svg 节点 HTML（给徽章用）
export function svgNode(path, size = 12) {
  return `<span class="ds-ico" style="display:inline-grid;place-items:center"><svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${path}</svg></span>`
}

// 拆分路径为 { file, dir }
export function splitPath(p) {
  const s = String(p || '').replace(/\\/g, '/')
  const i = s.lastIndexOf('/')
  return i < 0 ? { file: s, dir: '' } : { file: s.slice(i + 1), dir: s.slice(0, i) }
}

// 「非结构化表格库 · 某数据集」这类 label 的后半段
export function labelBranch(label) {
  const s = String(label || '')
  const i = s.indexOf(' · ')
  return i < 0 ? '' : s.slice(i + 3).trim()
}

// 行数格式化（中文千分位）
export function fmtRows(rows) {
  const n = Number(rows)
  return isNaN(n) ? String(rows) : n.toLocaleString('zh-CN')
}

// 构造普通问答来源项的展示与抽屉 payload
// item: { kind, label, name, tables, rows, sql, detail }
export function buildSourceItem(item) {
  const kind = SRC_TAGS[item.kind] ? item.kind : 'doc'
  const tag = SRC_TAGS[kind] || '引用'
  const branch = labelBranch(item.label)
  let title = ''
  let sub = ''
  const notes = []

  if (kind === 'database') {
    title = DB_FRIENDLY[item.name] || branch || item.name
    sub = 'MySQL · ' + item.name
  } else if (kind === 'tables') {
    title = branch || item.name
    sub = item.name
    if (item.detail) notes.push(item.detail)
  } else if (kind === 'knowledge') {
    const parts = splitPath(item.name)
    title = parts.file || item.name
    sub = parts.dir
    if (item.detail) notes.push(item.detail)
  } else if (kind === 'forecast') {
    const parts = String(item.detail || '').split(' · ').filter(Boolean)
    title = parts[0] || branch || item.name
    sub = branch ? '机器学习预测 · ' + branch : ''
    notes.push(...parts.slice(1))
  } else if (kind === 'chart') {
    const m = String(item.detail || '').match(/《([^》]+)》/)
    title = m ? m[1] : branch || '生成图表'
    const rest = String(item.detail || '').split('，').slice(1).join('，').trim()
    if (rest) notes.push(rest)
  }

  const detailRows = [['类型', tag], ['名称', title]]
  if (sub) detailRows.push(['位置', sub])
  if (item.rows != null) detailRows.push(['数据量', fmtRows(item.rows) + ' 行'])
  if (item.label && item.label !== title) detailRows.push(['来源标识', item.label])

  return {
    kind,
    tag,
    title,
    sub,
    notes: notes.filter(Boolean),
    tables: kind === 'tables' ? [] : (item.tables || []).slice(0, 12),
    sql: item.sql || '',
    rows: item.rows,
    label: item.label,
    detailRows,
  }
}

// 构造深度搜索引用项的展示与抽屉 payload
// item: { index, source, chunk_index, page, snippet }
export function buildDeepItem(item) {
  const parts = splitPath(item.source)
  const tag = item.index != null ? '引用 [' + item.index + ']' : '引用'
  const title = parts.file || item.source || '知识库文档'
  const sub = parts.dir
  const pills = []
  if (item.chunk_index != null) pills.push('第 ' + item.chunk_index + ' 段')
  if (item.page) pills.push('PDF 第 ' + item.page + ' 页')

  return {
    kind: 'knowledge',
    tag,
    title,
    sub,
    notes: [],
    tables: [],
    sql: '',
    rows: null,
    label: '',
    detailRows: [
      ['类型', '知识库引用'],
      ['文档', title],
      ['位置', sub || '（根目录）'],
    ],
    pills,
    snippet: item.snippet || '',
  }
}
