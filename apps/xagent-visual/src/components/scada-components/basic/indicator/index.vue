<template>
  <div class="indicator-container">
    <div class="indicator-light" :style="indicatorStyle"></div>
    <div v-if="binding" class="indicator-label">
      {{ binding.pointDescription || binding.pointName }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { useComponentBinding } from '@/composables/useComponentBinding'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const indicatorConfig = computed(() => props.config.indicatorConfig)
const binding = computed(() => props.config.binding)

const { currentValue } = useComponentBinding(binding, {
  autoRefresh: true,
  refreshInterval: 3000,
  transform: (value) => value === true || value === 1
})

const indicatorStyle = computed(() => ({
  backgroundColor: currentValue.value
    ? indicatorConfig.value?.onColor || '#27ae60'
    : indicatorConfig.value?.offColor || '#95a5a6',
  boxShadow: currentValue.value
    ? `0 0 20px ${indicatorConfig.value?.onColor || '#27ae60'}80`
    : 'none'
}))
</script>

<style scoped>
.indicator-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.indicator-light {
  width: 70%;
  height: 70%;
  border-radius: 50%;
  transition: all 0.3s ease;
}

.indicator-label {
  font-size: 10px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
