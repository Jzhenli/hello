<template>
  <div class="switch-container" @click="handleToggle">
    <div class="switch-label">{{ switchConfig?.onText || t('scadaComponents.switchOn') }}</div>
    <div class="switch-track" :class="{ on: currentValue, writing }">
      <div class="switch-thumb" :class="{ on: currentValue }"></div>
    </div>
    <div class="switch-label">{{ switchConfig?.offText || t('scadaComponents.switchOff') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ScadaComponent } from '@/types/scada'
import { useComponentBinding } from '@/composables/useComponentBinding'
import { ElMessageBox, ElMessage } from 'element-plus'

const { t } = useI18n()
const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const switchConfig = computed(() => props.config.switchConfig)
const binding = computed(() => props.config.binding)

const { currentValue, writeValue } = useComponentBinding(binding, {
  autoRefresh: true,
  refreshInterval: 3000,
  transform: (value) => value === true || value === 1
})

const writing = ref(false)

const handleToggle = async () => {
  if (props.editing) return
  
  if (switchConfig.value?.confirmRequired) {
    try {
      await ElMessageBox.confirm(
        `${t('scadaComponents.confirmToggle')}${currentValue.value ? t('scadaComponents.switchOff') : t('scadaComponents.switchOn')}${t('scadaComponents.confirmToggleSuffix', '？')}`,
        t('scadaComponents.operationConfirm'),
        { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
      )
    } catch {
      return
    }
  }

  const targetValue = !currentValue.value
  const writeTarget = switchConfig.value?.writePoint || binding.value

  if (writeTarget) {
    writing.value = true
    try {
      const res = await writeValue(targetValue)
      if (res.success) {
        ElMessage.success(t('scadaComponents.commandSent'))
      } else {
        ElMessage.error(res.message)
      }
    } catch (e: unknown) {
      const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : t('scadaComponents.operationFailed'))
      ElMessage.error(detail)
    } finally {
      writing.value = false
    }
  } else {
    currentValue.value = targetValue
  }
}
</script>

<style scoped>
.switch-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--bg-container);
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
}

.switch-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.switch-track {
  width: 50px;
  height: 26px;
  background: var(--border-base);
  border-radius: 13px;
  position: relative;
  transition: background 0.3s;
}

.switch-track.on {
  background: var(--color-success);
}

.switch-track.writing {
  opacity: 0.7;
}

.switch-thumb {
  position: absolute;
  width: 22px;
  height: 22px;
  background: var(--bg-container);
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.3s;
  box-shadow: var(--shadow-light);
}

.switch-thumb.on {
  transform: translateX(24px);
}
</style>