<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  content: { type: String, default: '' },
})

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 配置 marked：代码块带语言标签+复制按钮；图片仅放行同源 /... 或 http(s)
marked.use({
  renderer: {
    code({ text, lang }) {
      const label = ((lang || 'code').trim().slice(0, 16)) || 'code'
      const body = escapeHtml(String(text).replace(/\n$/, ''))
      return `<div class="codeblock"><div class="cb-head"><span class="cb-lang">${escapeHtml(label)}</span>`
        + `<button type="button" class="copy-code" data-copied="0">复制</button></div>`
        + `<pre><code>${body}</code></pre></div>`
    },
    image({ href, title, text }) {
      const src = href || ''
      const safe = /^https?:\/\//i.test(src) || (src.startsWith('/') && !src.includes('..'))
      const noWeird = !/[\s"'<>]/.test(src)
      if (safe && noWeird) {
        const alt = escapeHtml(text || '')
        const t = title ? ` title="${escapeHtml(title)}"` : ''
        return `<div class="md-img"><img src="${escapeHtml(src)}" alt="${alt}" loading="lazy"${t} /></div>`
      }
      return ''
    },
  },
})

const html = computed(() => {
  if (!props.content) return ''
  let out = marked.parse(props.content)
  // 表格外包 .tbl-wrap（marked 默认只输出 <table>）
  out = out.replace(/<table>/g, '<div class="tbl-wrap"><table>').replace(/<\/table>/g, '</table></div>')
  return out
})

function fallbackCopy(text, done) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.cssText = 'position:fixed;opacity:0'
  document.body.appendChild(ta)
  ta.select()
  try { document.execCommand('copy'); done() } catch (_) { /* noop */ }
  ta.remove()
}

function onClick(event) {
  const btn = event.target.closest('.copy-code')
  if (!btn) return
  const block = btn.closest('.codeblock')
  const pre = block ? block.querySelector('pre') : null
  if (!pre) return
  const text = pre.innerText
  const done = () => {
    btn.textContent = '已复制'
    btn.dataset.copied = '1'
    setTimeout(() => { btn.textContent = '复制'; btn.dataset.copied = '0' }, 1400)
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done))
  } else {
    fallbackCopy(text, done)
  }
}
</script>

<template>
  <div class="ai-content markdown-view" @click="onClick" v-html="html"></div>
</template>
