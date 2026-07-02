<template>
  <div 
    ref="canvasRef"
    class="scada-canvas"
    :style="{
      width: `${panel?.width || 1200}px`,
      height: `${panel?.height || 800}px`,
      backgroundColor: panel?.backgroundColor || '#f0f2f5',
      backgroundImage: panel?.backgroundImage ? `url(${panel.backgroundImage})` : 'none',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      transform: `scale(${scadaStore.zoom})`,
      transformOrigin: 'top left'
    }"
    @drop="handleDrop"
    @dragover="handleDragOver"
    @click="handleCanvasClick"
    @contextmenu.prevent="handleCanvasContextMenu"
    @mousedown="handleCanvasMouseDown"
    @mousemove="handleCanvasMouseMove"
    @mouseenter="handleCanvasMouseEnter"
    @mouseleave="handleCanvasMouseLeave"
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
        selected: selectedIds.includes(comp.id),
        'multi-selected': selectedIds.length > 1,
        locked: comp.locked,
        editing: isEditing
      }"
      :style="getComponentStyle(comp)"
      @mousedown="handleComponentMouseDown($event, comp)"
      @click="handleComponentClick($event, comp)"
      @contextmenu.prevent="handleContextMenu($event, comp)"
    >
      <!-- Component Content -->
      <component
        :is="getComponent(comp.type)"
        v-if="getComponent(comp.type)"
        :config="comp"
        :editing="isEditing"
      />
      
      <!-- Selection Handles (only show for primary selected component) -->
      <template v-if="selectedId === comp.id && isEditing && selectedIds.length === 1">
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

    <!-- Box Selection Rectangle -->
    <div 
      v-if="isBoxSelecting"
      class="selection-box"
      :style="{
        left: `${Math.min(boxSelectStart.x, boxSelectEnd.x)}px`,
        top: `${Math.min(boxSelectStart.y, boxSelectEnd.y)}px`,
        width: `${Math.abs(boxSelectEnd.x - boxSelectStart.x)}px`,
        height: `${Math.abs(boxSelectEnd.y - boxSelectStart.y)}px`
      }"
    />

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

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import type { ComponentType, ScadaComponent } from '@/types/scada'
import { getComponent } from './scada-components'
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

// Box selection state
const isBoxSelecting = ref(false)
const boxSelectStart = ref({ x: 0, y: 0 })
const boxSelectEnd = ref({ x: 0, y: 0 })
const justFinishedBoxSelect = ref(false)

// Multi-drag state (non-reactive, only used during drag)
let multiDragStartPositions: Map<string, { x: number, y: number }> = new Map()

// Mouse position tracking for paste
const mouseCanvasPos = ref({ x: 0, y: 0 })
const isMouseOnCanvas = ref(false)

const handleCanvasMouseMove = (e: MouseEvent) => {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  mouseCanvasPos.value = {
    x: (e.clientX - rect.left) / scadaStore.zoom,
    y: (e.clientY - rect.top) / scadaStore.zoom
  }
}

const handleCanvasMouseEnter = () => {
  isMouseOnCanvas.value = true
}

const handleCanvasMouseLeave = () => {
  isMouseOnCanvas.value = false
}

// Context menu state
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextMenuTargetId = ref<string | null>(null)
const contextMenuType = ref<'node' | 'canvas'>('canvas') // 区分右键的是节点还是画布

const panel = computed(() => scadaStore.currentPanel)
const components = computed(() => panel.value?.components || [])
const selectedId = computed(() => scadaStore.selectedComponentId)
const selectedIds = computed(() => scadaStore.selectedComponentIds)
const isEditing = computed(() => scadaStore.isEditing)
const targetComponent = computed(() => {
  if (!contextMenuTargetId.value || !panel.value) return null
  return panel.value.components.find(c => c.id === contextMenuTargetId.value) || null
})

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

  // If component is part of multi-selection, enable multi-drag
  if (selectedIds.value.length > 1 && selectedIds.value.includes(comp.id)) {
    // Don't call selectComponent here to preserve multi-selection
    isDragging.value = true
    dragStartPos.value = { x: e.clientX, y: e.clientY }
    
    // Save start positions for all selected components
    multiDragStartPositions = new Map()
    selectedIds.value.forEach(id => {
      const c = components.value.find(c => c.id === id)
      if (c) {
        multiDragStartPositions.set(id, { x: c.x, y: c.y })
      }
    })

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return
  }

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
    
    // Multi-drag: move all selected components
    if (selectedIds.value.length > 1 && multiDragStartPositions.size > 0) {
      selectedIds.value.forEach(id => {
        const startPos = multiDragStartPositions.get(id)
        if (startPos) {
          const newX = Math.max(0, startPos.x + dx)
          const newY = Math.max(0, startPos.y + dy)
          scadaStore.moveComponent(id, newX, newY)
        }
      })
      return
    }
    
    // Single drag
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
  multiDragStartPositions = new Map()
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
  // Don't clear selection if we just finished box selecting
  if (justFinishedBoxSelect.value) {
    justFinishedBoxSelect.value = false
    return
  }
  
  if (e.target === canvasRef.value) {
    scadaStore.selectComponent(null)
  }
  hideContextMenu()
}

const handleCanvasMouseDown = (e: MouseEvent) => {
  if (!isEditing.value || e.target !== canvasRef.value) return
  // Only start box selection on left click without modifiers
  if (e.button === 0 && !e.ctrlKey && !e.shiftKey && !e.metaKey) {
    e.preventDefault()
    isBoxSelecting.value = true
    const rect = canvasRef.value!.getBoundingClientRect()
    boxSelectStart.value = {
      x: (e.clientX - rect.left) / scadaStore.zoom,
      y: (e.clientY - rect.top) / scadaStore.zoom
    }
    boxSelectEnd.value = { ...boxSelectStart.value }
    
    // Clear selection
    scadaStore.clearSelection()
    
    document.addEventListener('mousemove', handleBoxSelectMove)
    document.addEventListener('mouseup', handleBoxSelectUp)
  }
}

const handleBoxSelectMove = (e: MouseEvent) => {
  if (!isBoxSelecting.value || !canvasRef.value) return
  
  const rect = canvasRef.value.getBoundingClientRect()
  boxSelectEnd.value = {
    x: (e.clientX - rect.left) / scadaStore.zoom,
    y: (e.clientY - rect.top) / scadaStore.zoom
  }
  
  // Calculate selection box
  const x1 = Math.min(boxSelectStart.value.x, boxSelectEnd.value.x)
  const y1 = Math.min(boxSelectStart.value.y, boxSelectEnd.value.y)
  const x2 = Math.max(boxSelectStart.value.x, boxSelectEnd.value.x)
  const y2 = Math.max(boxSelectStart.value.y, boxSelectEnd.value.y)
  
  // Find components within the selection box
  const selectedIds: string[] = []
  components.value.forEach(comp => {
    const compX2 = comp.x + comp.style.width
    const compY2 = comp.y + comp.style.height
    
    // Check if component intersects with selection box
    if (compX2 > x1 && comp.x < x2 && compY2 > y1 && comp.y < y2) {
      selectedIds.push(comp.id)
    }
  })
  
  if (selectedIds.length > 0) {
    scadaStore.selectComponent(selectedIds[0])
    scadaStore.selectedComponentIds = selectedIds
  } else {
    scadaStore.clearSelection()
  }
}

const handleBoxSelectUp = () => {
  isBoxSelecting.value = false
  justFinishedBoxSelect.value = true
  document.removeEventListener('mousemove', handleBoxSelectMove)
  document.removeEventListener('mouseup', handleBoxSelectUp)
}

const handleComponentClick = (e: MouseEvent, comp: ScadaComponent) => {
  if (!isEditing.value || comp.locked) return
  
  // Ctrl+Click: toggle selection
  if (e.ctrlKey || e.metaKey) {
    e.stopPropagation()
    const idx = selectedIds.value.indexOf(comp.id)
    if (idx >= 0) {
      // Deselect this component
      const newIds = selectedIds.value.filter(id => id !== comp.id)
      if (newIds.length > 0) {
        scadaStore.selectComponent(newIds[0])
        scadaStore.selectedComponentIds = newIds
      } else {
        scadaStore.clearSelection()
      }
    } else {
      // Add to selection
      scadaStore.selectComponent(comp.id)
      scadaStore.selectedComponentIds = [...selectedIds.value, comp.id]
    }
    return
  }
  
  // Shift+Click: select range
  if (e.shiftKey && selectedId.value) {
    e.stopPropagation()
    const allIds = components.value.map(c => c.id)
    const startIdx = allIds.indexOf(selectedId.value)
    const endIdx = allIds.indexOf(comp.id)
    if (startIdx >= 0 && endIdx >= 0) {
      const minIdx = Math.min(startIdx, endIdx)
      const maxIdx = Math.max(startIdx, endIdx)
      const rangeIds = allIds.slice(minIdx, maxIdx + 1)
      scadaStore.selectComponent(comp.id)
      scadaStore.selectedComponentIds = rangeIds
    }
    return
  }
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

  if (!isEditing.value || !isMouseOnCanvas.value) return

  // Ctrl+A: 全选所有组件
  if (e.ctrlKey && e.key === 'a') {
    e.preventDefault()
    scadaStore.selectAllComponents()
    return
  }

  // Ctrl+Z: 撤销（占位）
  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    return
  }

  // Ctrl+Y: 重做（占位）
  if (e.ctrlKey && e.key === 'y') {
    e.preventDefault()
    return
  }

  // Ctrl+C: 复制
  if (e.ctrlKey && e.key === 'c' && selectedId.value && !contextMenuVisible.value) {
    e.preventDefault()
    if (selectedIds.value.length > 1) {
      scadaStore.copySelectedComponents()
    } else {
      scadaStore.copyComponent(selectedId.value)
    }
    return
  }

  // Ctrl+V: 粘贴到鼠标位置
  if (e.ctrlKey && e.key === 'v' && !contextMenuVisible.value) {
    e.preventDefault()
    scadaStore.pasteComponent(mouseCanvasPos.value.x, mouseCanvasPos.value.y)
    return
  }

  // Delete / Backspace: 删除
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId.value) {
    e.preventDefault()
    if (selectedIds.value.length > 1) {
      scadaStore.deleteSelectedComponents()
    } else {
      scadaStore.deleteComponent(selectedId.value)
    }
    return
  }

  // Ctrl+D: 复制并粘贴到旁边
  if (e.ctrlKey && e.key === 'd' && selectedId.value) {
    e.preventDefault()
    scadaStore.duplicateComponent(selectedId.value)
    return
  }

  if (!selectedId.value) return

  const comp = scadaStore.selectedComponent
  if (!comp || comp.locked) return

  const step = panel.value?.grid || 20
  let moved = false

  switch (e.key) {
    case 'ArrowLeft':
      if (selectedIds.value.length > 1) {
        selectedIds.value.forEach(id => {
          const c = components.value.find(comp => comp.id === id)
          if (c && !c.locked) {
            scadaStore.moveComponent(id, c.x - step, c.y)
          }
        })
      } else {
        scadaStore.moveComponent(selectedId.value, comp.x - step, comp.y)
      }
      moved = true
      break
    case 'ArrowRight':
      if (selectedIds.value.length > 1) {
        selectedIds.value.forEach(id => {
          const c = components.value.find(comp => comp.id === id)
          if (c && !c.locked) {
            scadaStore.moveComponent(id, c.x + step, c.y)
          }
        })
      } else {
        scadaStore.moveComponent(selectedId.value, comp.x + step, comp.y)
      }
      moved = true
      break
    case 'ArrowUp':
      if (selectedIds.value.length > 1) {
        selectedIds.value.forEach(id => {
          const c = components.value.find(comp => comp.id === id)
          if (c && !c.locked) {
            scadaStore.moveComponent(id, c.x, c.y - step)
          }
        })
      } else {
        scadaStore.moveComponent(selectedId.value, comp.x, comp.y - step)
      }
      moved = true
      break
    case 'ArrowDown':
      if (selectedIds.value.length > 1) {
        selectedIds.value.forEach(id => {
          const c = components.value.find(comp => comp.id === id)
          if (c && !c.locked) {
            scadaStore.moveComponent(id, c.x, c.y + step)
          }
        })
      } else {
        scadaStore.moveComponent(selectedId.value, comp.x, comp.y + step)
      }
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

// Watch for scroll-to-component requests
watch(
  () => scadaStore.scrollToComponentId,
  async (newVal) => {
    const targetId = newVal ?? null
    if (!targetId || !canvasRef.value) return

    const component = components.value.find(c => c.id === targetId)
    if (!component) return

    await nextTick()

    const canvasContainer = canvasRef.value.closest('.canvas-wrapper')
    if (!canvasContainer) return

    const containerRect = canvasContainer.getBoundingClientRect()

    const scaledX = component.x * scadaStore.zoom
    const scaledY = component.y * scadaStore.zoom
    const scaledWidth = component.style.width * scadaStore.zoom
    const scaledHeight = component.style.height * scadaStore.zoom

    const componentCenterX = scaledX + scaledWidth / 2
    const componentCenterY = scaledY + scaledHeight / 2

    const containerCenterX = containerRect.width / 2
    const containerCenterY = containerRect.height / 2

    const scrollLeft = componentCenterX - containerCenterX
    const scrollTop = componentCenterY - containerCenterY

    canvasContainer.scrollTo({
      left: scrollLeft,
      top: scrollTop,
      behavior: 'smooth'
    })

    scadaStore.clearScrollTarget()
  }
)
</script>

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

.selection-box {
  position: absolute;
  border: 1px dashed var(--color-primary);
  background-color: rgba(64, 158, 255, 0.1);
  pointer-events: none;
  z-index: 1000;
}

.hidden-file-input {
  display: none;
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

.scada-component.selected.multi-selected {
  outline: 2px dashed var(--color-primary);
  background-color: rgba(64, 158, 255, 0.05);
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