<script setup>
const props = defineProps({
  status: { type: String, default: '' },
})
</script>

<template>
  <div v-if="status" class="ai-status">
    <span class="pulse"></span>
    <span>{{ status }}</span>
  </div>
</template>
