<script setup lang="ts">
import { computed } from 'vue'
import { NODE_TEMPLATES, type NodeType } from '@/types/rule'
import { useResponsive } from '@/utils/useResponsive'

const emit = defineEmits<{
  (e: 'dragStart', type: NodeType, event: DragEvent): void
}>()

const { isTablet, isMobile } = useResponsive()

const onDragStart = (type: NodeType, event: DragEvent) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', type)
    event.dataTransfer.effectAllowed = 'move'
  }
  emit('dragStart', type, event)
}

const categories = computed(() => {
  const cats: Record<string, typeof NODE_TEMPLATES> = {}
  NODE_TEMPLATES.forEach(template => {
    if (!cats[template.category]) {
      cats[template.category] = []
    }
    cats[template.category].push(template)
  })
  return cats
})

const paletteWidth = computed(() => {
  if (isMobile.value) return '180px'
  if (isTablet.value) return '200px'
  return '220px'
})
</script>

<template>
  <div class="node-palette" :style="{ width: paletteWidth }">
    <div class="palette-header">
      <h3>节点面板</h3>
      <p class="hint">拖拽节点到画布</p>
    </div>
    
    <div class="palette-body">
      <div v-for="(templates, category) in categories" :key="category" class="category-section">
        <div class="category-title">{{ category }}</div>
        <div
          v-for="template in templates"
          :key="template.type"
          class="palette-item"
          :class="{ 'touch-item': isTablet || isMobile }"
          :style="{ '--node-color': template.color }"
          draggable="true"
          @dragstart="onDragStart(template.type, $event)"
        >
          <div class="item-icon">{{ template.icon }}</div>
          <div class="item-info">
            <div class="item-label">{{ template.label }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-palette {
  background: #fff;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.palette-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.palette-header h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: #2c3e50;
}

.palette-header .hint {
  margin: 0;
  font-size: 12px;
  color: #95a5a6;
}

.palette-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.category-section {
  margin-bottom: 16px;
}

.category-title {
  font-size: 12px;
  font-weight: 600;
  color: #7f8c8d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-left: 4px;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  background: #fff;
  border: 2px solid var(--node-color);
  border-radius: 8px;
  cursor: grab;
  transition: all 0.2s ease;
  -webkit-user-select: none;
  user-select: none;
}

.palette-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.palette-item:active {
  cursor: grabbing;
  transform: scale(0.98);
}

.palette-item.touch-item {
  padding: 14px;
  margin-bottom: 10px;
  min-height: 56px;
}

.palette-item.touch-item:active {
  background: #f5f7fa;
  transform: scale(0.98);
}

.item-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--node-color);
  border-radius: 8px;
  font-size: 18px;
  flex-shrink: 0;
}

.touch-item .item-icon {
  width: 40px;
  height: 40px;
  font-size: 20px;
}

.item-info {
  flex: 1;
}

.item-label {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.touch-item .item-label {
  font-size: 15px;
}

@media (max-width: 1024px) {
  .palette-header {
    padding: 12px;
  }
  
  .palette-header h3 {
    font-size: 15px;
  }
  
  .palette-body {
    padding: 10px;
  }
  
  .category-title {
    font-size: 11px;
  }
}

@media (max-width: 768px) {
  .palette-header {
    padding: 10px;
  }
  
  .palette-header h3 {
    font-size: 14px;
  }
  
  .palette-header .hint {
    font-size: 11px;
  }
  
  .palette-body {
    padding: 8px;
  }
  
  .category-section {
    margin-bottom: 12px;
  }
  
  .category-title {
    font-size: 10px;
    margin-bottom: 6px;
  }
}
</style>
