<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const handleBack = () => {
  router.push({ name: 'ScadaList' })
}
</script>

<template>
  <div class="graphic-editor-container">
    <div class="header">
      <el-button :icon="ArrowLeft" @click="handleBack">
        {{ $t('scada.backToList') }}
      </el-button>
      <h2>{{ $t('scada.graphicEditor') }}</h2>
    </div>

    <div class="empty-editor">
      <el-empty :description="$t('scada.graphicPlaceholder')" />
    </div>
  </div>
</template>

<style scoped>
.graphic-editor-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #ebeef5;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.empty-editor {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
</style>
