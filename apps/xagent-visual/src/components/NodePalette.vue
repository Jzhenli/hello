<template>
  <div class="node-palette" :style="{ width: paletteWidth }">
    <div class="palette-header">
      <h3>{{ t('ruleNodes.nodePanel') }}</h3>
      <p class="hint">{{ t('ruleNodes.dragHint') }}</p>
    </div>
    
    <div class="palette-body">
      <div v-for="(templates, category) in categories" :key="category" class="category-section">
        <div class="category-title">{{ t(category) }}</div>
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
            <div class="item-label">{{ t(template.label) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NODE_TEMPLATES, type NodeType } from '@/types/rule'
import { useResponsive } from '@/utils/useResponsive'

const { t } = useI18n()

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
    const catKey = template.category
    if (!cats[catKey]) {
      cats[catKey] = []
    }
    cats[catKey].push(template)
  })
  return cats
})

const paletteWidth = computed(() => {
  if (isMobile.value) return '180px'
  if (isTablet.value) return '200px'
  return '220px'
})
</script>

<style scoped>
.node-palette {
  background: var(--bg-container);
  border-right: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.palette-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-base);
  background: var(--bg-hover);
}

.palette-header h3 {
  margin: 0 0 4px 0;
  font-size: 16px;
  color: var(--text-primary);
}

.palette-header .hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
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
  color: var(--text-secondary);
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
  background: var(--bg-container);
  border: 2px solid var(--node-color);
  border-radius: 8px;
  cursor: grab;
  transition: all 0.2s ease;
  -webkit-user-select: none;
  user-select: none;
}

.palette-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
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
  background: var(--bg-hover);
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
  color: var(--text-primary);
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
