<script setup>
import { watch, nextTick, ref, onMounted, onBeforeUnmount } from 'vue'
import { useConfirm } from '../composables/useConfirm'

const { state, resolveOk, resolveCancel } = useConfirm()
const cancelBtn = ref(null)

function onKeydown(e) {
  if (!state.open) return
  if (e.key === 'Escape') {
    e.preventDefault()
    resolveCancel()
  }
}

// 打开时焦点在"取消"
watch(
  () => state.open,
  async (open) => {
    if (open) {
      await nextTick()
      cancelBtn.value?.focus()
    }
  }
)

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div class="confirm-mask" :class="{ show: state.open }" @click.self="resolveCancel">
      <div v-if="state.open" class="confirm-box" role="dialog" aria-modal="true" :aria-label="state.title">
        <b>{{ state.title }}</b>
        <p v-if="state.text">{{ state.text }}</p>
        <div class="confirm-actions">
          <button ref="cancelBtn" type="button" class="confirm-cancel" @click="resolveCancel">
            {{ state.cancelText }}
          </button>
          <button
            type="button"
            class="confirm-ok"
            :class="{ danger: state.danger }"
            @click="resolveOk"
          >
            {{ state.okText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
