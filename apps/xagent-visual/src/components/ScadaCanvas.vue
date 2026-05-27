<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useScadaStore } from '@/stores/scada'
import type { ComponentType, ScadaComponent } from '@/types/scada'
import ScadaGauge from './components/ScadaGauge.vue'
import ScadaChart from './components/ScadaChart.vue'
import ScadaIndicator from './components/ScadaIndicator.vue'
import ScadaSwitch from './components/ScadaSwitch.vue'
import ScadaText from './components/ScadaText.vue'
import ScadaButton from './components/ScadaButton.vue'

const scadaStore = useScadaStore()

const canvasRef = ref<HTMLElement | null>(null)
const isDragging = ref(false)
const isResizing = ref(false)
const dragStartPos = ref({ x: 0, y: 0 })
const componentStartPos = ref({ x: 0, y: 0 })
const resizeStartSize = ref({ width: 0, height: 0 })
const resizeHandle = ref<string | null>(null)

const panel = computed(() => scadaStore.currentPanel)
const components = computed(() => panel.value?.components || [])
const selectedId = computed(() => scadaStore.selectedComponentId)
const isEditing = computed(() => scadaStore.isEditing)

const componentMap: Record<string, any> = {
  gauge: ScadaGauge,
  'chart-line': ScadaChart,
  'chart-bar': ScadaChart,
  indicator: ScadaIndicator,
  switch: ScadaSwitch,
  text: ScadaText,
  button: ScadaButton
}

const getComponentStyle = (comp: ScadaComponent) => ({
  left: `${comp.x}px`,
  top: `${comp.y}px`,
  width: `${comp.style.width}px`,
  height: `${comp.style.height}px`,
  opacity: comp.style.opacity || 1,
  zIndex: components.value.indexOf(comp)
})

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  if (!isEditing.value || !canvasRef.value) return

  const type = e.dataTransfer?.getData('component-type') as ComponentType
  if (!type) return

  const rect = canvasRef.value.getBoundingClientRect()
  const x = (e.clientX - rect.left) / scadaStore.zoom
  const y = (e.clientY - rect.top) / scadaStore.zoom

  const component = scadaStore.addComponent(type, x, y)
  if (component) {
    scadaStore.selectComponent(component.id)
  }
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const handleComponentMouseDown = (e: MouseEvent, comp: ScadaComponent) => {
  if (!isEditing.value || comp.locked) return
  e.stopPropagation()

  scadaStore.selectComponent(comp.id)
  isDragging.value = true
  dragStartPos.value = { x: e.clientX, y: e.clientY }
  componentStartPos.value = { x: comp.x, y: comp.y }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const handleMouseMove = (e: MouseEvent) => {
  if (!selectedId.value || !panel.value) return

  if (isDragging.value) {
    const dx = (e.clientX - dragStartPos.value.x) / scadaStore.zoom
    const dy = (e.clientY - dragStartPos.value.y) / scadaStore.zoom
    
    const newX = Math.max(0, Math.min(
      panel.value.width - (scadaStore.selectedComponent?.style.width || 0),
      componentStartPos.value.x + dx
    ))
    const newY = Math.max(0, Math.min(
      panel.value.height - (scadaStore.selectedComponent?.style.height || 0),
      componentStartPos.value.y + dy
    ))
    
    scadaStore.moveComponent(selectedId.value, newX, newY)
  }

  if (isResizing.value && resizeHandle.value) {
    const comp = scadaStore.selectedComponent
    if (!comp) return

    const dx = (e.clientX - dragStartPos.value.x) / scadaStore.zoom
    const dy = (e.clientY - dragStartPos.value.y) / scadaStore.zoom

    let newWidth = resizeStartSize.value.width
    let newHeight = resizeStartSize.value.height

    if (resizeHandle.value.includes('e')) {
      newWidth = Math.max(50, resizeStartSize.value.width + dx)
    }
    if (resizeHandle.value.includes('s')) {
      newHeight = Math.max(50, resizeStartSize.value.height + dy)
    }
    if (resizeHandle.value.includes('w')) {
      newWidth = Math.max(50, resizeStartSize.value.width - dx)
    }
    if (resizeHandle.value.includes('n')) {
      newHeight = Math.max(50, resizeStartSize.value.height - dy)
    }

    scadaStore.resizeComponent(selectedId.value, newWidth, newHeight)
  }
}

const handleMouseUp = () => {
  isDragging.value = false
  isResizing.value = false
  resizeHandle.value = null
  document.removeEventListener('mousemove', handleMouseMove)
  document.removeEventListener('mouseup', handleMouseUp)
}

const handleResizeStart = (e: MouseEvent, handle: string) => {
  if (!isEditing.value || !scadaStore.selectedComponent) return
  e.stopPropagation()

  isResizing.value = true
  resizeHandle.value = handle
  dragStartPos.value = { x: e.clientX, y: e.clientY }
  resizeStartSize.value = {
    width: scadaStore.selectedComponent.style.width,
    height: scadaStore.selectedComponent.style.height
  }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const handleCanvasClick = (e: MouseEvent) => {
  if (e.target === canvasRef.value) {
    scadaStore.selectComponent(null)
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (!isEditing.value || !selectedId.value) return

  if (e.key === 'Delete' || e.key === 'Backspace') {
    scadaStore.deleteComponent(selectedId.value)
  }

  if (e.ctrlKey && e.key === 'd') {
    e.preventDefault()
    scadaStore.duplicateComponent(selectedId.value)
  }

  const comp = scadaStore.selectedComponent
  if (!comp || comp.locked) return

  const step = panel.value?.grid || 20
  let moved = false

  switch (e.key) {
    case 'ArrowLeft':
      scadaStore.moveComponent(selectedId.value, comp.x - step, comp.y)
      moved = true
      break
    case 'ArrowRight':
      scadaStore.moveComponent(selectedId.value, comp.x + step, comp.y)
      moved = true
      break
    case 'ArrowUp':
      scadaStore.moveComponent(selectedId.value, comp.x, comp.y - step)
      moved = true
      break
    case 'ArrowDown':
      scadaStore.moveComponent(selectedId.value, comp.x, comp.y + step)
      moved = true
      break
  }

  if (moved) {
    e.preventDefault()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div 
    ref="canvasRef"
    class="scada-canvas"
    :style="{
      width: `${panel?.width || 1200}px`,
      height: `${panel?.height || 800}px`,
      backgroundColor: panel?.backgroundColor || '#f0f2f5',
      transform: `scale(${scadaStore.zoom})`,
      transformOrigin: 'top left'
    }"
    @drop="handleDrop"
    @dragover="handleDragOver"
    @click="handleCanvasClick"
  >
    <!-- Grid -->
    <div 
      v-if="scadaStore.showGrid && isEditing"
      class="canvas-grid"
      :style="{
        backgroundSize: `${panel?.grid || 20}px ${panel?.grid || 20}px`
      }"
    />
    
    <!-- Components -->
    <div
      v-for="comp in components"
      :key="comp.id"
      class="scada-component"
      :class="{ 
        selected: selectedId === comp.id, 
        locked: comp.locked,
        editing: isEditing
      }"
      :style="getComponentStyle(comp)"
      @mousedown="handleComponentMouseDown($event, comp)"
    >
      <!-- Component Content -->
      <component
        :is="componentMap[comp.type]"
        v-if="componentMap[comp.type]"
        :config="comp"
        :editing="isEditing"
      />
      
      <!-- Selection Handles -->
      <template v-if="selectedId === comp.id && isEditing">
        <div class="resize-handle nw" @mousedown.stop="handleResizeStart($event, 'nw')"></div>
        <div class="resize-handle n" @mousedown.stop="handleResizeStart($event, 'n')"></div>
        <div class="resize-handle ne" @mousedown.stop="handleResizeStart($event, 'ne')"></div>
        <div class="resize-handle e" @mousedown.stop="handleResizeStart($event, 'e')"></div>
        <div class="resize-handle se" @mousedown.stop="handleResizeStart($event, 'se')"></div>
        <div class="resize-handle s" @mousedown.stop="handleResizeStart($event, 's')"></div>
        <div class="resize-handle sw" @mousedown.stop="handleResizeStart($event, 'sw')"></div>
        <div class="resize-handle w" @mousedown.stop="handleResizeStart($event, 'w')"></div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.scada-canvas {
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.canvas-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.05) 1px, transparent 1px);
  pointer-events: none;
}

.scada-component {
  position: absolute;
  cursor: move;
  user-select: none;
}

.scada-component.editing:hover {
  outline: 1px dashed #3498db;
}

.scada-component.selected {
  outline: 2px solid #3498db;
  box-shadow: 0 0 10px rgba(52, 152, 219, 0.3);
}

.scada-component.locked {
  cursor: not-allowed;
  opacity: 0.7;
}

.resize-handle {
  position: absolute;
  width: 10px;
  height: 10px;
  background: #3498db;
  border: 2px solid #fff;
  border-radius: 2px;
  z-index: 10;
}

.resize-handle.nw { top: -5px; left: -5px; cursor: nw-resize; }
.resize-handle.n { top: -5px; left: 50%; transform: translateX(-50%); cursor: n-resize; }
.resize-handle.ne { top: -5px; right: -5px; cursor: ne-resize; }
.resize-handle.e { top: 50%; right: -5px; transform: translateY(-50%); cursor: e-resize; }
.resize-handle.se { bottom: -5px; right: -5px; cursor: se-resize; }
.resize-handle.s { bottom: -5px; left: 50%; transform: translateX(-50%); cursor: s-resize; }
.resize-handle.sw { bottom: -5px; left: -5px; cursor: sw-resize; }
.resize-handle.w { top: 50%; left: -5px; transform: translateY(-50%); cursor: w-resize; }
</style>
