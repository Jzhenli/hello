<template>
  <div class="container-wrapper" :style="containerStyle">
    <div v-if="editing" class="container-placeholder">
      <span>容器</span>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const containerStyle = computed(() => ({
  backgroundColor: props.config.style.backgroundColor || 'transparent',
  borderColor: props.config.style.borderColor || 'var(--border-base)',
  borderWidth: `${props.config.style.borderWidth || 1}px`,
  borderRadius: `${props.config.style.borderRadius || 4}px`,
}))
</script>

<style scoped>
.container-wrapper {
  width: 100%;
  height: 100%;
  border-style: solid;
  position: relative;
  overflow: hidden;
}

.container-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--text-placeholder);
  font-size: 14px;
  pointer-events: none;
  opacity: 0.5;
}
</style>