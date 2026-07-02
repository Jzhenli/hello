<template>
  <div class="component-palette">
    <div class="palette-header">
      <div class="header-content">
        <span class="header-title">{{ t('componentPalette.title') }}</span>
        <div class="header-toggle" @click="emit('toggleList')" :title="props.showComponentList ? '隐藏组件列表' : '显示组件列表'">
          <el-icon><DArrowLeft v-if="props.showComponentList" /><DArrowRight v-else /></el-icon>
        </div>
      </div>
    </div>
    
    <div class="palette-body">
      <!-- Category menu -->
      <div class="category-menu">
        <div
          v-for="category in categories"
          :key="category.key"
          class="menu-item"
          :class="{ 'active': activeCategory === category.key }"
          @click="selectCategory(category.key)"
        >
          <span class="menu-icon">{{ category.icon }}</span>
          <span class="menu-label">{{ t(`scadaComponentCategories.${category.key}`) }}</span>
        </div>
      </div>

      <!-- Component grid -->
      <div class="component-panel">
        <div v-if="activeComponents.length === 0" class="empty-category">
          {{ $t('scada.noComponents') }}
        </div>
        <div v-else class="component-grid">
          <div
            v-for="template in activeComponents"
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

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { type ComponentType } from '@/types/scada'
import {
  getSortedCategories,
  getComponentsByCategory
} from '@/config/component-categories'
import { DArrowLeft, DArrowRight } from '@element-plus/icons-vue'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'dragStart', type: ComponentType): void
  (e: 'toggleList'): void
}>()

const props = defineProps<{
  showComponentList?: boolean
}>()

// Active category state
const activeCategory = ref<string>('basic')

// Get all categories sorted by order
const categories = computed(() => getSortedCategories())

// Get components for active category
const activeComponents = computed(() => {
  return getComponentsByCategory(activeCategory.value)
})

const onDragStart = (type: ComponentType, event: DragEvent) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('component-type', type)
    event.dataTransfer.effectAllowed = 'copy'
  }
  emit('dragStart', type)
}

const selectCategory = (key: string) => {
  activeCategory.value = key
}
</script>

<style scoped>
.component-palette {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-container);
}

.palette-header {
  height: 44px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-base);
  background: var(--bg-hover);
  flex-shrink: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  gap: 8px;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.palette-hint {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-light);
}

.header-toggle {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
  flex-shrink: 0;
}

.header-toggle:hover {
  background: var(--bg-hover);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.palette-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* Category menu sidebar */
.category-menu {
  width: 70px;
  flex-shrink: 0;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-base);
  overflow-y: auto;
  padding: 8px 0;
}

.menu-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  cursor: pointer;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.menu-item:hover {
  background: var(--bg-hover);
}

.menu-item.active {
  background: var(--color-primary-light-9, rgba(64, 158, 255, 0.1));
  border-left-color: var(--color-primary);
}

.menu-icon {
  font-size: 20px;
  line-height: 1;
}

.menu-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.2;
}

.menu-item.active .menu-label {
  color: var(--color-primary);
  font-weight: 500;
}

/* Component panel */
.component-panel {
  flex: 1;
  padding: 10px;
  overflow-y: auto;
}

.empty-category {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
  padding: 20px;
}

.component-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.component-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1 / 1;
  padding: 8px;
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
  font-size: 28px;
  margin-bottom: 4px;
  line-height: 1;
}

.component-name {
  font-size: 11px;
  color: var(--text-primary);
  text-align: center;
  line-height: 1.2;
  word-break: keep-all;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
</style>