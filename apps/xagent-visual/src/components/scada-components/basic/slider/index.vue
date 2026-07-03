<template>
  <div class="slider-container">
    <div v-if="binding" class="slider-label">
      {{ binding.pointDescription || binding.pointName }}
    </div>
    <div class="slider-body">
      <el-slider
        v-model="sliderValue"
        :min="min"
        :max="max"
        :step="step"
        :disabled="editing"
        show-input
        input-size="small"
      />
    </div>
    <div class="slider-value">{{ currentValue }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { useComponentBinding } from '@/composables/useComponentBinding'
import { ElSlider, ElMessage } from 'element-plus'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const sliderConfig = computed(() => props.config.sliderConfig)
const binding = computed(() => props.config.binding)

const { currentValue, boundPoint, writeValue } = useComponentBinding(binding, {
  autoRefresh: true,
  refreshInterval: 3000,
  transform: (value) => typeof value === 'number' ? value : 0
})

const min = computed(() => sliderConfig.value?.min ?? 0)
const max = computed(() => sliderConfig.value?.max ?? 100)
const step = computed(() => sliderConfig.value?.step ?? 1)

const sliderValue = computed({
  get: () => currentValue.value,
  set: (val: number) => {
    if (!props.editing && boundPoint.value) {
      writeValue(val)
      ElMessage.success('已写入')
    }
  }
})
</script>

<style scoped>
.slider-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-container);
  border-radius: 6px;
  padding: 12px;
  gap: 8px;
}

.slider-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  max-width: 90%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slider-body {
  width: 90%;
}

.slider-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
</style>