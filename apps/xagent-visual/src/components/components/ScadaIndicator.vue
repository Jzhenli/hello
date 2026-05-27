<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { usePointStore } from '@/stores/points'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const pointStore = usePointStore()

const indicatorConfig = computed(() => props.config.indicatorConfig)
const binding = computed(() => props.config.binding)

const isOn = ref(false)

onMounted(() => {
  if (binding.value) {
    const device = pointStore.devices.find(d => d.asset === binding.value!.deviceId || d.name === binding.value!.deviceId)
    const point = device?.points.find(p => p.name === binding.value!.pointName)
    if (point) {
      isOn.value = point.currentValue === true || point.currentValue === 1
    }
  }
})

const indicatorStyle = computed(() => ({
  backgroundColor: isOn.value 
    ? indicatorConfig.value?.onColor || '#27ae60'
    : indicatorConfig.value?.offColor || '#95a5a6',
  boxShadow: isOn.value 
    ? `0 0 20px ${indicatorConfig.value?.onColor || '#27ae60'}80`
    : 'none'
}))
</script>

<template>
  <div class="indicator-container">
    <div class="indicator-light" :style="indicatorStyle"></div>
    <div v-if="binding" class="indicator-label">
      {{ binding.pointDescription || binding.pointName }}
    </div>
  </div>
</template>

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
  color: #7f8c8d;
  margin-top: 4px;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
