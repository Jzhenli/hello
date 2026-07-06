<template>
  <div class="preview-page" :class="{ fullscreen: isFullscreen }">
    <div v-if="!isFullscreen" class="preview-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" size="small" @click="handleGoBack">
          {{ $t('scada.backToList') }}
        </el-button>
        <h3 class="panel-title">{{ currentPanel?.name }}</h3>
        <el-tag type="warning" size="small">{{ $t('scada.graphicType') }}</el-tag>
      </div>
      <div class="header-right">
        <el-button :icon="FullScreen" size="small" @click="handleToggleFullscreen">
          {{ $t('scada.fullscreen') }}
        </el-button>
      </div>
    </div>

    <div v-if="currentPanel" class="preview-content">
      <div class="blank-canvas">
        <GraphicSingle ref="graphicSingle" />
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useScadaStore } from '@/stores/scada'
import { ArrowLeft, FullScreen } from '@element-plus/icons-vue'
import GraphicSingle from './GraphicSingle.vue'

const route = useRoute()
const router = useRouter()
const scadaStore = useScadaStore()

const isFullscreen = ref(false)

const currentPanel = computed(() => scadaStore.currentPanel)

onMounted(() => {
  const panelId = route.params.id as string
  if (panelId) {
    scadaStore.selectPanel(panelId)
    scadaStore.isEditing = false
  }
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  scadaStore.isEditing = true
  scadaStore.isFullscreenPreview = false
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
})

const handleFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

const handleGoBack = () => {
  router.push({ name: 'ScadaList' })
}

const handleToggleFullscreen = async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen()
  } else {
    await document.exitFullscreen()
  }
}
</script>

<style scoped>
.preview-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-secondary);
}

.preview-page.fullscreen {
  height: 100vh;
}

.preview-header {
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

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.preview-content {
  flex: 1;
  overflow: auto;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #1a1a2e;
}

.blank-canvas {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--text-secondary);
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>