<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import type { ComponentType, ScadaComponent } from '@/types/scada'
import ScadaGauge from './components/ScadaGauge.vue'
import ScadaChart from './components/ScadaChart.vue'
import ScadaIndicator from './components/ScadaIndicator.vue'
import ScadaSwitch from './components/ScadaSwitch.vue'
import ScadaText from './components/ScadaText.vue'
import ScadaButton from './components/ScadaButton.vue'
import {
  CopyDocument,
  Document,
  Lock,
  Unlock,
  Delete,
  Top,
  Bottom
} from '@element-plus/icons-vue'

const { t } = useI18n()
const scadaStore = useScadaStore()

const canvasRef = ref<HTMLElement | null>(null)
const isDragging = ref(false)
const isResizing = ref(false)
const dragStartPos = ref({ x: 0, y: 0 })
const componentStartPos = ref({ x: 0, y: 0 })
const resizeStartSize = ref({ width: 0, height: 0 })
const resizeHandle = ref<string | null>(null)

// Context menu state
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextMenuTargetId = ref<string | null>(null)
const contextMenuType = ref<'node' | 'canvas'>('canvas') // 区分右键的是节点还是画布

const panel = computed(() => scadaStore.currentPanel)
const components = computed(() => panel.value?.components || [])
const selectedId = computed(() => scadaStore.selectedComponentId)
const isEditing = computed(() => scadaStore.isEditing)
const targetComponent = computed(() => {
  if (!contextMenuTargetId.value || !panel.value) return null
  return panel.value.components.find(c => c.id === contextMenuTargetId.value) || null
})

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
  hideContextMenu()
}

// Context menu handlers
const handleContextMenu = (e: MouseEvent, comp: ScadaComponent) => {
  if (!isEditing.value) return
  e.preventDefault()
  e.stopPropagation()

  scadaStore.selectComponent(comp.id)
  contextMenuTargetId.value = comp.id
  contextMenuPosition.value = { x: e.clientX, y: e.clientY }
  contextMenuType.value = 'node'
  contextMenuVisible.value = true
}

const handleCanvasContextMenu = (e: MouseEvent) => {
  if (!isEditing.value) return
  e.preventDefault()

  contextMenuTargetId.value = null
  contextMenuPosition.value = { x: e.clientX, y: e.clientY }
  contextMenuType.value = 'canvas'
  contextMenuVisible.value = true
}

const hideContextMenu = () => {
  contextMenuVisible.value = false
  contextMenuTargetId.value = null
}

const handleContextAction = (action: string) => {
  switch (action) {
    case 'copy':
      if (contextMenuTargetId.value) {
        scadaStore.copyComponent(contextMenuTargetId.value)
      }
      break
    case 'paste': {
      const rect = canvasRef.value?.getBoundingClientRect()
      if (rect) {
        const x = (contextMenuPosition.value.x - rect.left) / scadaStore.zoom
        const y = (contextMenuPosition.value.y - rect.top) / scadaStore.zoom
        scadaStore.pasteComponent(x, y)
      }
      break
    }
    case 'lock':
    case 'unlock':
      if (contextMenuTargetId.value) {
        scadaStore.toggleLock(contextMenuTargetId.value)
      }
      break
    case 'delete':
      if (contextMenuTargetId.value) {
        scadaStore.deleteComponent(contextMenuTargetId.value)
      }
      break
    case 'bringToFront':
      if (contextMenuTargetId.value) {
        scadaStore.bringToFront(contextMenuTargetId.value)
      }
      break
    case 'sendToBack':
      if (contextMenuTargetId.value) {
        scadaStore.sendToBack(contextMenuTargetId.value)
      }
      break
  }

  hideContextMenu()
}

const handleKeyDown = (e: KeyboardEvent) => {
  // Close context menu on Escape
  if (e.key === 'Escape' && contextMenuVisible.value) {
    hideContextMenu()
    return
  }

  if (!isEditing.value || !selectedId.value) return

  // Copy: Ctrl+C
  if (e.ctrlKey && e.key === 'c' && !contextMenuVisible.value) {
    e.preventDefault()
    scadaStore.copyComponent(selectedId.value)
    return
  }

  // Paste: Ctrl+V
  if (e.ctrlKey && e.key === 'v' && !contextMenuVisible.value) {
    e.preventDefault()
    scadaStore.pasteComponent()
    return
  }

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
    @contextmenu.prevent="handleCanvasContextMenu"
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
      @contextmenu.prevent="handleContextMenu($event, comp)"
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

    <!-- Context Menu -->
    <Teleport to="body">
      <div 
        v-if="contextMenuVisible && isEditing"
        class="context-menu-overlay"
        @click="hideContextMenu"
      >
        <div 
          class="context-menu"
          :style="{
            left: `${contextMenuPosition.x}px`,
            top: `${contextMenuPosition.y}px`
          }"
          @click.stop
        >
          <!-- Node context menu -->
          <template v-if="contextMenuType === 'node'">
            <div class="context-menu-item" @click="handleContextAction('copy')">
              <el-icon class="menu-icon"><CopyDocument /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.copy') }}</span>
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" @click="handleContextAction(targetComponent?.locked ? 'unlock' : 'lock')">
              <el-icon class="menu-icon">
                <component :is="targetComponent?.locked ? Unlock : Lock" />
              </el-icon>
              <span class="menu-label">{{ targetComponent?.locked ? t('scadaContextMenu.unlock') : t('scadaContextMenu.lock') }}</span>
            </div>
            <div class="context-menu-item" @click="handleContextAction('delete')">
              <el-icon class="menu-icon"><Delete /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.delete') }}</span>
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" @click="handleContextAction('bringToFront')">
              <el-icon class="menu-icon"><Top /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.bringToFront') }}</span>
            </div>
            <div class="context-menu-item" @click="handleContextAction('sendToBack')">
              <el-icon class="menu-icon"><Bottom /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.sendToBack') }}</span>
            </div>
          </template>
          <!-- Canvas context menu -->
          <template v-else>
            <div 
              v-if="scadaStore.clipboard"
              class="context-menu-item" 
              @click="handleContextAction('paste')"
            >
              <el-icon class="menu-icon"><Document /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.paste') }}</span>
            </div>
            <div v-else class="context-menu-item disabled">
              <el-icon class="menu-icon"><Document /></el-icon>
              <span class="menu-label">{{ t('scadaContextMenu.noClipboard') }}</span>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.scada-canvas {
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-base);
  border-radius: 4px;
}

.canvas-grid {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    linear-gradient(var(--grid-line, rgba(0, 0, 0, 0.05)) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line, rgba(0, 0, 0, 0.05)) 1px, transparent 1px);
  pointer-events: none;
}

.scada-component {
  position: absolute;
  cursor: move;
  user-select: none;
}

.scada-component.editing:hover {
  outline: 1px dashed var(--color-primary);
}

.scada-component.selected {
  outline: 2px solid var(--color-primary);
  box-shadow: 0 0 10px var(--color-primary-light);
}

.scada-component.locked {
  cursor: not-allowed;
  opacity: 0.7;
}

.resize-handle {
  position: absolute;
  width: 10px;
  height: 10px;
  background: var(--color-primary);
  border: 2px solid var(--bg-container);
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

.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
}

.context-menu {
  position: fixed;
  min-width: 180px;
  background: var(--bg-container, #fff);
  border: 1px solid var(--border-base, #e4e7ed);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(0, 0, 0, 0.08);
  padding: 6px 0;
  z-index: 10000;
  backdrop-filter: blur(8px);
  animation: contextMenuFadeIn 0.15s ease-out;
}

@keyframes contextMenuFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary, #303133);
  transition: all 0.15s ease;
  user-select: none;
}

.context-menu-item:hover {
  background-color: var(--color-primary-light, #ecf5ff);
  color: var(--color-primary, #409eff);
}

.context-menu-item:hover .menu-icon {
  color: var(--color-primary, #409eff);
}

.context-menu-item.danger {
  color: var(--color-danger, #f56c6c);
}

.context-menu-item.danger:hover {
  background-color: var(--color-danger-light, #fef0f0);
  color: var(--color-danger, #f56c6c);
}

.context-menu-item.danger:hover .menu-icon {
  color: var(--color-danger, #f56c6c);
}

.context-menu-item.disabled {
  cursor: not-allowed;
  opacity: 0.4;
  color: var(--text-secondary, #c0c4cc);
}

.context-menu-item.disabled:hover {
  background-color: transparent;
  color: var(--text-secondary, #c0c4cc);
}

.context-menu-item.disabled:hover .menu-icon {
  color: var(--text-secondary, #c0c4cc);
}

.menu-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--text-secondary, #909399);
  transition: color 0.15s ease;
}

.menu-label {
  flex: 1;
  white-space: nowrap;
}

.context-menu-divider {
  height: 1px;
  background-color: var(--border-light, #ebeef5);
  margin: 6px 12px;
}
</style>
