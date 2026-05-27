<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { usePointStore } from '@/stores/points'
import { controlApi } from '@/api/control'
import { ElMessageBox, ElMessage } from 'element-plus'

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
      `确定要执行 "${buttonConfig.value?.text || '操作'}" 吗？`,
      '操作确认',
      { confirmButtonText: '确定', cancelButtonText: '取消' }
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
        ElMessage.success('操作命令已下发')
      } else {
        ElMessage.error(`命令状态异常: ${res.status}`)
      }
    } catch (e: unknown) {
      const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : '操作失败')
      ElMessage.error(detail)
    } finally {
      writing.value = false
    }
  }
}
</script>

<template>
  <div class="button-container" @click="handleClick">
    <el-button 
      :type="buttonConfig?.type || 'primary'"
      size="default"
      :loading="writing"
      style="width: 100%; height: 100%;"
    >
      {{ buttonConfig?.text || '按钮' }}
    </el-button>
  </div>
</template>

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
