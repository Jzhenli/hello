<template>
  <div class="slideshow-container" :class="{ 'is-fullscreen': isFullscreen }">
    <div v-if="!isFullscreen" class="slideshow-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" size="small" @click="handleExit">
          {{ $t('scada.backToList') }}
        </el-button>
        <h3 class="slideshow-title">{{ $t('scada.slideshowPreview') }}</h3>
        <el-tag type="info" size="small">
          {{ currentIndex + 1 }} / {{ panels.length }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button :icon="VideoPlay" size="small" @click="togglePlay">
          {{ isPlaying ? $t('scada.slideshowPause') : $t('scada.slideshowPlay') }}
        </el-button>
        <el-button :icon="FullScreen" size="small" @click="handleToggleFullscreen">
          {{ $t('scada.fullscreen') }}
        </el-button>
      </div>
    </div>

    <div v-if="panels.length === 0" class="empty-state">
      <el-empty :description="$t('scada.noProjects')">
        <el-button type="primary" @click="handleExit">{{ $t('scada.backToProjectList') }}</el-button>
      </el-empty>
    </div>

    <div v-else class="slideshow-content">
      <div class="slideshow-wrapper">
        <transition :name="transitionName" mode="out-in">
          <div :key="currentPanel?.id" class="slideshow-slide">
            <div v-if="currentPanel?.type === 'Graphic'" class="slide-content">
              <GraphicSingle ref="graphicSingleRef" />
            </div>
            <div v-else class="slide-content">
              <ScadaCanvas ref="scadaCanvasRef" />
            </div>
          </div>
        </transition>
      </div>

      <div class="slideshow-controls">
        <el-button :icon="ArrowLeft" circle @click="handlePrev" :disabled="!canPrev" />
        <div class="slide-indicator">
          <span class="current-index">{{ currentIndex + 1 }}</span>
          <span class="separator">/</span>
          <span class="total-count">{{ panels.length }}</span>
        </div>
        <el-button :icon="ArrowRight" circle @click="handleNext" :disabled="!canNext" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import { ArrowLeft, ArrowRight, FullScreen, VideoPlay } from '@element-plus/icons-vue'
import ScadaCanvas from '@/components/ScadaCanvas.vue'
import GraphicSingle from '@/views/GraphicPreview/GraphicSingle.vue'
import type { SlideshowConfig } from './SlideshowConfig.vue'

const route = useRoute()
const router = useRouter()
const scadaStore = useScadaStore()
const { t } = useI18n()

const isFullscreen = ref(false)
const isPlaying = ref(false)
const currentIndex = ref(0)
const graphicSingleRef = ref()
const scadaCanvasRef = ref()

let playTimer: ReturnType<typeof setInterval> | null = null

const config = ref<SlideshowConfig>({
  interval: 5,
  loop: true,
  autoPlay: true,
  transition: 'fade',
  scope: 'all',
})

const panels = computed(() => {
  const allPanels = scadaStore.panels
  if (config.value.scope === 'all') {
    return allPanels
  }
  return allPanels.filter(p => p.type === config.value.scope)
})

const currentPanel = computed(() => panels.value[currentIndex.value])

const canPrev = computed(() => {
  if (config.value.loop) return true
  return currentIndex.value > 0
})

const canNext = computed(() => {
  if (config.value.loop) return true
  return currentIndex.value < panels.value.length - 1
})

const transitionName = computed(() => {
  if (config.value.transition === 'fade') return 'fade'
  if (config.value.transition === 'slide') return 'slide'
  return ''
})

onMounted(() => {
  const query = route.query
  config.value = {
    interval: Number(query.interval) || 5,
    loop: query.loop !== 'false',
    autoPlay: query.autoPlay !== 'false',
    transition: (query.transition as any) || 'fade',
    scope: (query.scope as any) || 'all',
  }

  scadaStore.isEditing = false
  scadaStore.isFullscreenPreview = true

  if (panels.value.length > 0) {
    scadaStore.selectPanel(panels.value[0].id)
    if (config.value.autoPlay) {
      startPlay()
    }
  }

  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  stopPlay()
  scadaStore.isEditing = true
  scadaStore.isFullscreenPreview = false
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('keydown', handleKeydown)
})

const handleFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowLeft') {
    handlePrev()
  } else if (e.key === 'ArrowRight') {
    handleNext()
  } else if (e.key === ' ') {
    e.preventDefault()
    togglePlay()
  } else if (e.key === 'Escape') {
    if (isFullscreen.value) {
      document.exitFullscreen()
    } else {
      handleExit()
    }
  }
}

const handleToggleFullscreen = async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen()
  } else {
    await document.exitFullscreen()
  }
}

const handleExit = () => {
  router.push({ name: 'ScadaList' })
}

const togglePlay = () => {
  if (isPlaying.value) {
    stopPlay()
  } else {
    startPlay()
  }
}

const startPlay = () => {
  isPlaying.value = true
  playTimer = setInterval(() => {
    if (canNext.value) {
      handleNext()
    } else if (config.value.loop) {
      currentIndex.value = 0
      scadaStore.selectPanel(panels.value[0].id)
    } else {
      stopPlay()
    }
  }, config.value.interval * 1000)
}

const stopPlay = () => {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

const handlePrev = () => {
  stopPlay()
  if (currentIndex.value > 0) {
    currentIndex.value--
    scadaStore.selectPanel(panels.value[currentIndex.value].id)
  } else if (config.value.loop) {
    currentIndex.value = panels.value.length - 1
    scadaStore.selectPanel(panels.value[currentIndex.value].id)
  }
}

const handleNext = () => {
  stopPlay()
  if (currentIndex.value < panels.value.length - 1) {
    currentIndex.value++
    scadaStore.selectPanel(panels.value[currentIndex.value].id)
  } else if (config.value.loop) {
    currentIndex.value = 0
    scadaStore.selectPanel(panels.value[0].id)
  }
}

watch(() => config.value.autoPlay, (val) => {
  if (val && !isPlaying.value) {
    startPlay()
  } else if (!val && isPlaying.value) {
    stopPlay()
  }
})
</script>

<style scoped>
.slideshow-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-secondary);
}

.slideshow-container.is-fullscreen {
  height: 100vh;
}

.slideshow-header {
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

.slideshow-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slideshow-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  position: relative;
}

.slideshow-wrapper {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  position: relative;
}

.slideshow-slide {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.slide-content {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  max-width: 100%;
  max-height: 100%;
}

.slideshow-controls {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 8px;
  backdrop-filter: blur(10px);
}

.slide-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.current-index {
  font-size: 20px;
}

.separator {
  opacity: 0.6;
}

.total-count {
  opacity: 0.8;
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.5s ease;
}

.slide-enter-from {
  transform: translateX(100%);
}

.slide-leave-to {
  transform: translateX(-100%);
}

@media (max-width: 768px) {
  .slideshow-controls {
    bottom: 10px;
    padding: 8px 16px;
    gap: 12px;
  }

  .slide-indicator {
    font-size: 14px;
  }

  .current-index {
    font-size: 16px;
  }
}
</style>
