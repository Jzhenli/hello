<template>
  <div class="gauge-container">
    <svg viewBox="0 0 100 70" class="gauge-svg">
      <!-- Background arc -->
      <path
        d="M 10 60 A 40 40 0 0 1 90 60"
        fill="none"
        stroke="var(--border-base)"
        stroke-width="8"
        stroke-linecap="round"
      />
      <!-- Value arc -->
      <path
        d="M 10 60 A 40 40 0 0 1 90 60"
        fill="none"
        :stroke="currentColor"
        stroke-width="8"
        stroke-linecap="round"
        :stroke-dasharray="strokeDasharray"
        stroke-dashoffset="0"
        transform="rotate(0, 50, 60)"
        class="gauge-arc"
      />
      <!-- Center point -->
      <circle cx="50" cy="60" r="3" :fill="currentColor" />
    </svg>
    
    <div class="gauge-value" :style="{ color: currentColor }">
      {{ displayValue }}
      <span v-if="gaugeConfig?.unit" class="unit">{{ gaugeConfig.unit }}</span>
    </div>
    
    <div v-if="binding" class="gauge-label">
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

const gaugeConfig = computed(() => props.config.gaugeConfig)
const binding = computed(() => props.config.binding)

const { currentValue } = useComponentBinding(binding, {
  autoRefresh: true,
  refreshInterval: 5000,
  transform: (value) => typeof value === 'number' ? value : 0
})

const percentage = computed(() => {
  if (!gaugeConfig.value) return 0
  const min = gaugeConfig.value.min
  const max = gaugeConfig.value.max
  return ((currentValue.value - min) / (max - min)) * 100
})

const currentColor = computed(() => {
  if (!gaugeConfig.value?.thresholds) return '#3498db'
  const thresholds = [...gaugeConfig.value.thresholds].sort((a, b) => b.value - a.value)
  for (const t of thresholds) {
    if (currentValue.value >= t.value) {
      return t.color
    }
  }
  return gaugeConfig.value.thresholds[0]?.color || '#3498db'
})

const strokeDasharray = computed(() => {
  const radius = 45
  const circumference = 2 * Math.PI * radius
  return `${(percentage.value / 100) * circumference} ${circumference}`
})

const displayValue = computed(() => {
  const val = currentValue.value
  return typeof val === 'number' ? val.toFixed(1) : '0.0'
})
</script>

<style scoped>
.gauge-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--bg-container) 0%, var(--bg-hover) 100%);
  border-radius: 8px;
  padding: 10px;
}

.gauge-svg {
  width: 80%;
  height: auto;
}

.gauge-arc {
  transition: stroke-dasharray 0.5s ease, stroke 0.3s ease;
}

.gauge-value {
  font-size: 24px;
  font-weight: 700;
  margin-top: -10px;
}

.gauge-value .unit {
  font-size: 14px;
  font-weight: 400;
  opacity: 0.7;
}

.gauge-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  text-align: center;
  max-width: 90%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>