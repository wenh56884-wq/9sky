<script setup>
import { computed } from 'vue'

const props = defineProps({
  plan: { type: Object, default: null },
})

const MARKS = { done: '✓', doing: '▶', pending: '○', skipped: '–', failed: '!' }

const steps = computed(() => (props.plan && props.plan.steps) ? props.plan.steps : [])

const progressText = computed(() => {
  if (!steps.value.length) return ''
  const done = steps.value.filter((s) => s.status === 'done' || s.status === 'skipped').length
  return done + '/' + steps.value.length + ' 步'
})

const showThinking = computed(() => props.plan && props.plan.thinking && !steps.value.length)
</script>

<template>
  <div v-if="plan" class="plan-panel">
    <div v-if="showThinking" class="plan-thinking">⏳ {{ plan.thinking }}</div>
    <template v-else>
      <div class="plan-head">
        <span class="plan-title">执行计划</span>
        <span v-if="plan.goal" class="plan-goal">{{ plan.goal }}</span>
        <span v-if="progressText" class="plan-progress">{{ progressText }}</span>
      </div>
      <div class="plan-steps">
        <div v-for="step in steps" :key="step.id" class="plan-step" :class="'st-' + (step.status || 'pending')">
          <span class="ps-icon">{{ MARKS[step.status] || '○' }}</span>
          <span class="ps-title">{{ step.title }}</span>
          <span v-if="step.note" class="ps-note">（{{ step.note }}）</span>
        </div>
      </div>
    </template>
  </div>
</template>
