<template>
  <div class="button-container" @click="handleClick">
    <el-button 
      :type="buttonConfig?.type || 'primary'"
      size="default"
      :loading="writing"
      style="width: 100%; height: 100%;"
    >
      {{ buttonConfig?.text || t('scadaComponents.defaultButton') }}
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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
const writing = ref(false)

const buttonConfig = computed(() => props.config.buttonConfig)

const handleClick = async () => {
  if (props.editing) return
  
  try {
    await ElMessageBox.confirm(
      t('scadaComponents.confirmExecute', { action: buttonConfig.value?.text || t('scadaComponents.defaultButton') }),
      t('scadaComponents.operationConfirm'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel') }
    )
  } catch {
    return
  }

  const writeTarget = buttonConfig.value?.writePoint
  if (writeTarget && buttonConfig.value?.writeValue !== undefined) {
    writing.value = true
    try {
      const device = pointStore.devices.find(d => d.asset === writeTarget.deviceId || d.name === writeTarget.deviceId)
      const pluginName = device?.pluginName || ''
      const res = await controlApi.writeSetpoint(
        pluginName,
        writeTarget.deviceId,
        writeTarget.pointName,
        buttonConfig.value.writeValue
      )
      if (res.status === 'ACCEPTED') {
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
  }
}
</script>

<style scoped>
.button-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}
</style>
