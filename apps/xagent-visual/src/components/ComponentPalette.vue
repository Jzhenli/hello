<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { COMPONENT_TEMPLATES, type ComponentType } from '@/types/scada'

const { t } = useI18n()

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
    const catKey = template.category
    if (!cats[catKey]) {
      cats[catKey] = []
    }
    cats[catKey].push(template)
  })
  return cats
})
</script>

<template>
  <div class="component-palette">
    <div class="palette-header">
      <h3>{{ t('componentPalette.title') }}</h3>
      <span class="hint">{{ t('componentPalette.dragHint') }}</span>
    </div>
    
    <div class="palette-body">
      <div v-for="(templates, category) in categories" :key="category" class="category-section">
        <div class="category-title">{{ t(category) }}</div>
        <div class="component-grid">
          <div
            v-for="template in templates"
            :key="template.type"
            class="component-item"
            draggable="true"
            @dragstart="onDragStart(template.type, $event)"
          >
            <div class="component-icon">{{ template.icon }}</div>
            <div class="component-name">{{ t(template.name) }}</div>
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
  background: var(--bg-container);
}

.palette-header {
  padding: 12px;
  border-bottom: 1px solid var(--border-base);
  background: var(--bg-hover);
  flex-shrink: 0;
}

.palette-header h3 {
  margin: 0 0 4px 0;
  font-size: 14px;
  color: var(--text-primary);
}

.palette-header .hint {
  font-size: 11px;
  color: var(--text-secondary);
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
  color: var(--text-secondary);
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
  background: var(--bg-hover);
  border: 1px solid var(--border-base);
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;
}

.component-item:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  transform: translateY(-1px);
  box-shadow: var(--shadow-light);
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
  color: var(--text-primary);
  text-align: center;
  line-height: 1.2;
}
</style>
