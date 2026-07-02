<template>
  <div class="component-list">
    <div class="list-header">
      <span class="header-title">{{ $t('scada.componentList') }}</span>
      <span class="header-count">{{ components.length }}</span>
    </div>
    
    <div class="list-content">
      <div v-if="components.length === 0" class="empty-list">
        {{ $t('scada.noComponents') }}
      </div>
      
      <div
        v-for="component in components"
        :key="component.id"
        class="list-item"
        :class="{ 'active': scadaStore.selectedComponentIds.includes(component.id) }"
        @click="handleLocateComponent(component)"
      >
        <div class="item-icon">{{ getComponentIcon(component.type) }}</div>
        <div class="item-info">
          <div class="item-name">{{ getComponentName(component) }}</div>
          <div class="item-position">X: {{ Math.round(component.x) }}, Y: {{ Math.round(component.y) }}</div>
        </div>
        <el-button
          :icon="Delete"
          size="small"
          text
          class="delete-btn"
          @click="handleDeleteComponent(component, $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import { Delete } from '@element-plus/icons-vue'

const { t } = useI18n()
const scadaStore = useScadaStore()

const components = computed(() => scadaStore.currentPanel?.components || [])

const getComponentName = (comp: any) => {
  if (comp.name?.startsWith('scadaComponentNames.')) {
    return t(comp.name)
  }
  return comp.name || comp.type
}

const handleLocateComponent = (component: any) => {
  scadaStore.selectComponent(component.id)
  scadaStore.scrollToComponent(component.id)
}

const handleDeleteComponent = (component: any, event: Event) => {
  event.stopPropagation()
  scadaStore.deleteComponent(component.id)
}

const getComponentIcon = (type: string) => {
  const iconMap: Record<string, string> = {
    'text': 'T',
    'image': '🖼',
    'button': '☐',
    'input': '▤',
    'chart': '📊',
    'gauge': '◐',
    'switch': '⊘',
    'slider': '▤',
    'progress': '▰',
    'indicator': '●',
    'valve': '⊗',
    'pump': '⚙',
    'pipe': '━',
    'tank': '▭',
  }
  return iconMap[type] || '☐'
}
</script>

<style scoped>
.component-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-container);
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid var(--border-base);
  flex-shrink: 0;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.header-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.empty-list {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
  padding: 20px;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.list-item:hover {
  background: var(--bg-hover);
}

.list-item.active {
  background: var(--color-primary-light-9, rgba(64, 158, 255, 0.1));
  border: 1px solid var(--color-primary, #409eff);
}

.list-item.active .item-icon {
  background: var(--color-primary, #409eff);
  color: #fff;
}

.list-item.active .item-name {
  color: var(--color-primary, #409eff);
  font-weight: 500;
}

.item-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 14px;
  flex-shrink: 0;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-position {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
  color: var(--text-secondary);
}

.list-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--color-danger);
}
</style>
