<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'
import { ElMessageBox } from 'element-plus'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const buttonConfig = computed(() => props.config.buttonConfig)

const handleClick = async () => {
  if (props.editing) return
  
  try {
    await ElMessageBox.confirm(
      `确定要执行 "${buttonConfig.value?.text || '操作'}" 吗？`,
      '操作确认',
      { confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    console.log('执行操作:', buttonConfig.value?.writeValue)
  } catch {
    // Cancelled
  }
}
</script>

<template>
  <div class="button-container" @click="handleClick">
    <el-button 
      :type="buttonConfig?.type || 'primary'"
      size="default"
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
