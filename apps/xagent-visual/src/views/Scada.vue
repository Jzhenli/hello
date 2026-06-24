<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useScadaStore } from '@/stores/scada'
import { useUserStore } from '@/stores/users'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FullScreen, View, Upload, ArrowLeft } from '@element-plus/icons-vue'
import ComponentPalette from '@/components/ComponentPalette.vue'
import ScadaCanvas from '@/components/ScadaCanvas.vue'
import ComponentConfig from '@/components/ComponentConfig.vue'

const route = useRoute()
const router = useRouter()
const scadaStore = useScadaStore()
const userStore = useUserStore()

const isPreviewMode = ref(false)

const currentPanel = computed(() => scadaStore.currentPanel)

// Get project ID from route params and select it
watch(() => route.params.id, (newId) => {
  if (newId) {
    scadaStore.selectPanel(newId as string)
  }
}, { immediate: true })

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
})

const handleGoBack = () => {
  router.push({ name: 'ScadaList' })
}

const handleFullscreenChange = () => {
  if (!document.fullscreenElement && scadaStore.isFullscreenPreview) {
    scadaStore.isFullscreenPreview = false
    isPreviewMode.value = false
    scadaStore.isEditing = true
  }
}

const handleZoomIn = () => {
  scadaStore.zoom = Math.min(2, scadaStore.zoom + 0.1)
}

const handleZoomOut = () => {
  scadaStore.zoom = Math.max(0.5, scadaStore.zoom - 0.1)
}

const handleZoomReset = () => {
  scadaStore.zoom = 1
}

const handleSave = () => {
  ElMessage.success('面板已保存')
}

const handlePreview = () => {
  isPreviewMode.value = true
  scadaStore.isEditing = false
}

const handleExitPreview = () => {
  scadaStore.isFullscreenPreview = false
  isPreviewMode.value = false
  scadaStore.isEditing = true
  
  if (document.fullscreenElement) {
    document.exitFullscreen()
  }
}

const handleFullscreen = () => {
  const elem = document.documentElement
  if (elem.requestFullscreen) {
    elem.requestFullscreen()
  }
  scadaStore.isFullscreenPreview = true
  isPreviewMode.value = true
  scadaStore.isEditing = false
}

const handlePublish = () => {
  ElMessageBox.confirm(
    '确定要发布当前面板吗？发布后其他用户将可以看到此面板。',
    '发布确认',
    { confirmButtonText: '发布', cancelButtonText: '取消', type: 'info' }
  ).then(() => {
    ElMessage.success('面板已发布成功！')
  }).catch(() => {})
}

const handleExport = () => {
  if (!currentPanel.value) return
  
  const data = JSON.stringify(currentPanel.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${currentPanel.value.name}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('面板已导出')
}
</script>

<template>
  <div class="scada-page" :class="{ 'preview-mode': isPreviewMode }">
    <div v-if="!isPreviewMode" class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="handleGoBack">返回列表</el-button>
        <span class="project-name">{{ currentPanel?.name }}</span>
      </div>
      <div class="header-actions">
        <el-button :icon="View" @click="handlePreview">预览</el-button>
        <el-button :icon="FullScreen" @click="handleFullscreen">全屏</el-button>
        <el-button @click="handleExport">导出</el-button>
        <el-button type="primary" :icon="Upload" v-if="userStore.hasPermission('scada', 'update')" @click="handlePublish">发布</el-button>
        <el-button v-if="userStore.hasPermission('scada', 'update')" @click="handleSave">保存</el-button>
      </div>
    </div>
    
    <div v-if="isPreviewMode" class="preview-header">
      <span class="preview-title">{{ currentPanel?.name }}</span>
      <div class="preview-actions">
        <el-button size="small" @click="handleExitPreview">退出预览</el-button>
      </div>
    </div>
    
    <div v-if="currentPanel" class="scada-editor">
      <div v-if="!isPreviewMode" class="editor-left">
        <ComponentPalette />
      </div>
      
      <div class="editor-center">
        <div v-if="!isPreviewMode" class="editor-toolbar">
          <div class="toolbar-left">
            <el-button-group>
              <el-button size="small" @click="handleZoomOut">-</el-button>
              <el-button size="small" @click="handleZoomReset">{{ Math.round(scadaStore.zoom * 100) }}%</el-button>
              <el-button size="small" @click="handleZoomIn">+</el-button>
            </el-button-group>
            <el-checkbox v-model="scadaStore.showGrid" size="small">显示网格</el-checkbox>
            <el-checkbox v-model="scadaStore.isEditing" size="small">编辑模式</el-checkbox>
          </div>
          <div class="toolbar-right">
            <span class="component-count">组件: {{ currentPanel.components.length }}</span>
          </div>
        </div>
        
        <div class="canvas-wrapper">
          <ScadaCanvas />
        </div>
      </div>
      
      <div v-if="!isPreviewMode" class="editor-right">
        <ComponentConfig />
      </div>
    </div>
    
    <div v-else class="empty-state">
      <el-empty description="项目不存在或已被删除">
        <el-button type="primary" @click="handleGoBack">返回项目列表</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.scada-page {
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  position: relative;
  z-index: 1;
  height: 100%;
}

.scada-page.preview-mode {
  background: #1a1a2e;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.project-name {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.preview-title {
  font-size: 16px;
  font-weight: 500;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.panel-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  overflow-x: auto;
  flex-shrink: 0;
}

.panel-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #f5f7fa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.panel-tab:hover {
  background: #e8f4fc;
}

.panel-tab.active {
  background: #3498db;
  color: #fff;
  border-color: #3498db;
}

.tab-name {
  font-size: 13px;
}

.tab-close {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 12px;
  opacity: 0.6;
}

.tab-close:hover {
  background: rgba(0, 0, 0, 0.1);
  opacity: 1;
}

.scada-editor {
  flex: 1;
  display: flex;
  min-height: 0;
  background: #e8e8e8;
  position: relative;
}

.preview-mode .scada-editor {
  background: #1a1a2e;
}

.editor-left {
  width: 200px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #dce1e6;
}

.editor-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.component-count {
  font-size: 12px;
  color: #7f8c8d;
}

.canvas-wrapper {
  flex: 1;
  overflow: auto;
  padding: 20px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.editor-right {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid #dce1e6;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #95a5a6;
  background: #f5f7fa;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-state p {
  margin: 0 0 16px 0;
  font-size: 14px;
}
</style>
