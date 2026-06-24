<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ScadaComponent } from '@/types/scada'
import { usePointStore } from '@/stores/points'
import { controlApi } from '@/api/control'
import { ElMessageBox, ElMessage } from 'element-plus'

const { t } = useI18n()
const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const pointStore = usePointStore()

const switchConfig = computed(() => props.config.switchConfig)
const binding = computed(() => props.config.binding)

const isOn = ref(false)
const writing = ref(false)

onMounted(() => {
  if (binding.value) {
    const device = pointStore.devices.find(d => d.asset === binding.value!.deviceId || d.name === binding.value!.deviceId)
    const point = device?.points.find(p => p.name === binding.value!.pointName)
    if (point) {
      isOn.value = point.currentValue === true || point.currentValue === 1
    }
  }
})

const handleToggle = async () => {
  if (props.editing) return
  
  if (switchConfig.value?.confirmRequired) {
    try {
      await ElMessageBox.confirm(
        `${t('scadaComponents.confirmToggle')}${isOn.value ? t('scadaComponents.switchOff') : t('scadaComponents.switchOn')}${t('scadaComponents.confirmToggleSuffix', '？')}`,
        t('scadaComponents.operationConfirm'),
        { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
      )
    } catch {
      return
    }
  }

  const targetValue = !isOn.value
  const writeTarget = switchConfig.value?.writePoint || binding.value

  if (writeTarget) {
    writing.value = true
    try {
      const device = pointStore.devices.find(d => d.asset === writeTarget.deviceId || d.name === writeTarget.deviceId)
      const pluginName = device?.pluginName || ''
      const res = await controlApi.writeSetpoint(
        pluginName,
        writeTarget.deviceId,
        writeTarget.pointName,
        targetValue
      )
      if (res.status === 'ACCEPTED') {
        isOn.value = targetValue
        ElMessage.success(t('scadaComponents.commandSent'))
      } else {
        ElMessage.error(`${t('scadaComponents.commandError')}: ${res.status}`)
      }
    } catch (e: unknown) {
      const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : t('scadaComponents.operationFailed'))
      ElMessage.error(detail)
    } finally {
      writing.value = false
    }
  } else {
    isOn.value = targetValue
  }
}
</script>

<template>
  <div class="switch-container" @click="handleToggle">
    <div class="switch-label">{{ switchConfig?.onText || t('scadaComponents.switchOn') }}</div>
    <div class="switch-track" :class="{ on: isOn, writing }">
      <div class="switch-thumb" :class="{ on: isOn }"></div>
    </div>
    <div class="switch-label">{{ switchConfig?.offText || t('scadaComponents.switchOff') }}</div>
  </div>
</template>

<style scoped>
.switch-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
}

.switch-label {
  font-size: 12px;
  color: #7f8c8d;
}

.switch-track {
  width: 50px;
  height: 26px;
  background: #dce1e6;
  border-radius: 13px;
  position: relative;
  transition: background 0.3s;
}

.switch-track.on {
  background: #27ae60;
}

.switch-track.writing {
  opacity: 0.7;
}

.switch-thumb {
  position: absolute;
  width: 22px;
  height: 22px;
  background: #fff;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.switch-thumb.on {
  transform: translateX(24px);
}
</style>
