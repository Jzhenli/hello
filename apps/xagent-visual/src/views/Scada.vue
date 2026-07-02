<template>
  <div class="scada-page" :class="{ 'preview-mode': isPreviewMode }">
    <div v-if="!isPreviewMode" class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="handleGoBack">{{ $t('scada.backToList') }}</el-button>
        <span class="project-name">{{ currentPanel?.name }}</span>
      </div>
      <div class="header-actions">
        <el-button :icon="View" @click="handlePreview">{{ $t('scada.preview') }}</el-button>
        <el-button :icon="FullScreen" @click="handleFullscreen">{{ $t('scada.fullscreen') }}</el-button>
        <el-button @click="handleExport">{{ $t('common.export') }}</el-button>
        <el-button type="primary" :icon="Upload" v-if="userStore.hasPermission('scada', 'update')" @click="handlePublish">{{ $t('scada.publish') }}</el-button>
        <el-button v-if="userStore.hasPermission('scada', 'update')" @click="handleSave">{{ $t('common.save') }}</el-button>
      </div>
    </div>
    
    <div v-if="isPreviewMode" class="preview-header">
      <span class="preview-title">{{ currentPanel?.name }}</span>
      <div class="preview-actions">
        <el-button size="small" @click="handleExitPreview">{{ $t('scada.exitPreview') }}</el-button>
      </div>
    </div>
    
    <div v-if="currentPanel" class="scada-editor">
      <div v-if="!isPreviewMode" class="editor-left">
        <ComponentPalette :showComponentList="showComponentList" @toggleList="showComponentList = !showComponentList" />
      </div>
      
      <div v-if="!isPreviewMode" class="editor-list" :class="{ collapsed: !showComponentList }">
        <div v-if="showComponentList" class="list-panel">
          <ComponentList />
        </div>
      </div>
      
      <div class="editor-center">
        <div v-if="!isPreviewMode" class="editor-toolbar">
          <div class="toolbar-left">
            <el-button-group>
              <el-button size="small" @click="handleZoomOut">-</el-button>
              <el-button size="small" @click="handleZoomReset">{{ Math.round(scadaStore.zoom * 100) }}%</el-button>
              <el-button size="small" @click="handleZoomIn">+</el-button>
            </el-button-group>
            <el-checkbox v-model="scadaStore.showGrid" size="small">{{ $t('scada.showGrid') }}</el-checkbox>
            <el-checkbox v-model="scadaStore.isEditing" size="small">{{ $t('scada.editMode') }}</el-checkbox>
            <el-popover
              placement="bottom-start"
              :width="320"
              trigger="hover"
            >
              <template #reference>
                <el-button size="small" text class="shortcut-btn">
                  ⌨️ {{ $t('scada.shortcuts') }}
                </el-button>
              </template>
              <div class="shortcut-list">
                <div class="shortcut-item">
                  <span class="key-group"><kbd>Ctrl</kbd> + <kbd>C</kbd></span>
                  <span class="desc">{{ $t('scada.copy') }}</span>
                </div>
                <div class="shortcut-item">
                  <span class="key-group"><kbd>Ctrl</kbd> + <kbd>V</kbd></span>
                  <span class="desc">{{ $t('scada.paste') }}</span>
                </div>
                <div class="shortcut-item">
                  <span class="key-group"><kbd>Ctrl</kbd> + <kbd>D</kbd></span>
                  <span class="desc">{{ $t('scada.duplicate') }}</span>
                </div>
                <div class="shortcut-item">
                  <span class="key-group"><kbd>Delete</kbd></span>
                  <span class="desc">{{ $t('scada.delete') }}</span>
                </div>
                <div class="shortcut-item">
                  <span class="key-group"><kbd>←</kbd><kbd>→</kbd><kbd>↑</kbd><kbd>↓</kbd></span>
                  <span class="desc">{{ $t('scada.move') }}</span>
                </div>
                <div class="shortcut-item">
                  <span class="key-group"><kbd>Esc</kbd></span>
                  <span class="desc">{{ $t('scada.closeMenu') }}</span>
                </div>
              </div>
            </el-popover>
          </div>
          <div class="toolbar-right">
            <span class="component-count">{{ $t('scada.componentCount', { count: currentPanel.components.length }) }}</span>
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
      <el-empty :description="$t('scada.projectNotExist')">
        <el-button type="primary" @click="handleGoBack">{{ $t('scada.backToProjectList') }}</el-button>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import { useUserStore } from '@/stores/users'
import { usePointStore } from '@/stores/points'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FullScreen, View, Upload, ArrowLeft } from '@element-plus/icons-vue'
import ComponentPalette from '@/components/ComponentPalette.vue'
import ComponentList from '@/components/ComponentList.vue'
import ScadaCanvas from '@/components/ScadaCanvas.vue'
import ComponentConfig from '@/components/ComponentConfig.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const scadaStore = useScadaStore()
const userStore = useUserStore()
const pointStore = usePointStore()

const isPreviewMode = ref(false)
const showComponentList = ref(false)

const currentPanel = computed(() => scadaStore.currentPanel)

// Get project ID from route params and select it
watch(() => route.params.id, (newId) => {
  if (newId) {
    scadaStore.selectPanel(newId as string)
  }
}, { immediate: true })

onMounted(async () => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  await pointStore.fetchDevicesWithPoints()
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
  ElMessage.success(t('scada.savePanelSuccess'))
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
    t('scada.publishConfirm'),
    t('scada.publishConfirmTitle'),
    { confirmButtonText: t('scada.publish'), cancelButtonText: t('common.cancel'), type: 'info' }
  ).then(() => {
    ElMessage.success(t('scada.publishSuccess'))
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
  ElMessage.success(t('scada.exportSuccess'))
}
</script>

<style scoped>
.scada-page {
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
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
  background: var(--bg-container);
  border-bottom: 1px solid var(--border-base);
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
  color: var(--text-primary);
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
  background: var(--bg-container);
  border-bottom: 1px solid var(--border-base);
  overflow-x: auto;
  flex-shrink: 0;
}

.panel-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-base);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.panel-tab:hover {
  background: var(--bg-hover);
}

.panel-tab.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
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
  background: var(--bg-secondary);
  position: relative;
}

.preview-mode .scada-editor {
  background: #1a1a2e;
}

.editor-left {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-container);
  border-right: 1px solid var(--border-base);
}

.editor-list {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-container);
  border-right: 1px solid var(--border-base);
  transition: width 0.2s ease;
  position: relative;
  display: flex;
  flex-direction: column;
}

.editor-list.collapsed {
  width: 0;
  overflow: hidden;
}

.editor-list .list-panel {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.editor-list .list-toggle {
  position: absolute;
  top: 50%;
  right: -14px;
  transform: translateY(-50%);
  width: 28px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-container);
  border: 1px solid var(--border-base);
  border-radius: 0 8px 8px 0;
  cursor: pointer;
  z-index: 10;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.editor-list .list-toggle:hover {
  background: var(--bg-hover);
  color: var(--color-primary);
}

.editor-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.editor-toolbar {
  height: 44px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  background: var(--bg-container);
  border-bottom: 1px solid var(--border-base);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.shortcut-btn {
  font-size: 12px;
  padding: 0 8px;
  color: var(--text-secondary);
  cursor: pointer;
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shortcut-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0;
  font-size: 13px;
}

.key-group {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  font-size: 12px;
  font-family: inherit;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-base);
  border-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  min-width: 20px;
  height: 20px;
}

.desc {
  color: var(--text-secondary);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.component-count {
  font-size: 12px;
  color: var(--text-secondary);
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
  background: var(--bg-container);
  border-left: 1px solid var(--border-base);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: var(--bg-secondary);
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