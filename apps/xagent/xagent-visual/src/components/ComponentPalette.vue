<script setup lang="ts">
import { computed } from 'vue'
import { COMPONENT_TEMPLATES, type ComponentType } from '@/types/scada'

const emit = defineEmits<{
  (e: 'dragStart', type: ComponentType): void
}>()

const onDragStart = (type: ComponentType, event: DragEvent) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('component-type', type)
    event.dataTransfer.effectAllowed = 'copy'
  }
  emit('dragStart', type)
}

const categories = computed(() => {
  const cats: Record<string, typeof COMPONENT_TEMPLATES> = {}
  COMPONENT_TEMPLATES.forEach(template => {
    if (!cats[template.category]) {
      cats[template.category] = []
    }
    cats[template.category].push(template)
  })
  return cats
})
</script>

<template>
  <div class="component-palette">
    <div class="palette-header">
      <h3>📦 组件库</h3>
      <span class="hint">拖拽到画布</span>
    </div>
    
    <div class="palette-body">
      <div v-for="(templates, category) in categories" :key="category" class="category-section">
        <div class="category-title">{{ category }}</div>
        <div class="component-grid">
          <div
            v-for="template in templates"
            :key="template.type"
            class="component-item"
            draggable="true"
            @dragstart="onDragStart(template.type, $event)"
          >
            <div class="component-icon">{{ template.icon }}</div>
            <div class="component-name">{{ template.name }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.component-palette {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.palette-header {
  padding: 12px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
  flex-shrink: 0;
}

.palette-header h3 {
  margin: 0 0 4px 0;
  font-size: 14px;
  color: #2c3e50;
}

.palette-header .hint {
  font-size: 11px;
  color: #95a5a6;
}

.palette-body {
  flex: 1;
  padding: 8px;
  overflow-y: auto;
}

.category-section {
  margin-bottom: 12px;
}

.category-title {
  font-size: 11px;
  font-weight: 600;
  color: #7f8c8d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  padding-left: 4px;
}

.component-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.component-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;
}

.component-item:hover {
  background: #e8f4fc;
  border-color: #3498db;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(52, 152, 219, 0.2);
}

.component-item:active {
  cursor: grabbing;
  transform: scale(0.95);
}

.component-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.component-name {
  font-size: 11px;
  color: #2c3e50;
  text-align: center;
  line-height: 1.2;
}
</style>
