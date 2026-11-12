<script setup>
const props = defineProps({
  trace: { type: Object, default: null },
})
</script>

<template>
  <div v-if="trace" class="deep-trace">
    <div v-if="trace.info" class="dt-row">{{ trace.info }}</div>

    <div v-if="trace.plan && trace.plan.length">
      <div class="dt-head">检索计划 · 拆解为多个子问题</div>
      <div>
        <span v-for="q in trace.plan" :key="q" class="dt-chip">{{ q }}</span>
      </div>
    </div>

    <div v-for="(s, i) in (trace.search || [])" :key="i" class="dt-row">
      · 子检索「{{ s.query }}」
      <span class="hit"> 命中 {{ s.hits ?? 0 }} 段</span>
      <span>（{{ s.engines }} · 第{{ s.round }}轮）</span>
    </div>

    <div v-if="trace.gap && trace.gap.length">
      <div class="dt-head">查漏补缺 · 补充检索</div>
      <div>
        <span v-for="q in trace.gap" :key="q" class="dt-chip">{{ q }}</span>
      </div>
    </div>

    <div v-if="trace.rerank" class="dt-row">{{ trace.rerank }}</div>
    <div v-if="trace.fail" class="dt-row deep-err">{{ trace.fail }}</div>
  </div>
</template>
