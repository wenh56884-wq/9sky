<script setup>
import { useToast } from '../composables/useToast'

const { toasts } = useToast()
</script>

<template>
  <div class="toast-host" aria-live="polite">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="['toast-' + t.type, { 'fade-out': t.leaving }]"
    >{{ t.text }}</div>
  </div>
</template>
