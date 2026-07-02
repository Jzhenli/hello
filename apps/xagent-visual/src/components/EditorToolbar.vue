<template>
  <div class="editor-toolbar" :class="{ 'mobile-toolbar': isMobile, 'tablet-toolbar': isTablet }">
    <div class="toolbar-left">
      <h2 class="toolbar-title">{{ t('editorToolbar.title') }}</h2>
    </div>
    
    <div v-if="showStats" class="toolbar-center">
      <div class="stats">
        <span class="stat-item">
          <span class="stat-label">{{ t('editorToolbar.nodes') }}:</span>
          <span class="stat-value">{{ nodeCount }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">{{ t('editorToolbar.edges') }}:</span>
          <span class="stat-value">{{ edgeCount }}</span>
        </span>
      </div>
    </div>
    
    <div class="toolbar-right">
      <button class="toolbar-btn" @click="emit('import')" :title="t('editorToolbar.importRule')">
        <span class="btn-icon">📥</span>
        <span class="btn-text">{{ t('editorToolbar.import') }}</span>
      </button>
      <button class="toolbar-btn" @click="emit('export')" :title="t('editorToolbar.exportRule')">
        <span class="btn-icon">📤</span>
        <span class="btn-text">{{ t('editorToolbar.export') }}</span>
      </button>
      <button class="toolbar-btn danger" @click="emit('clear')" :title="t('editorToolbar.clearCanvas')">
        <span class="btn-icon">🗑️</span>
        <span class="btn-text">{{ t('editorToolbar.clear') }}</span>
      </button>
      <button 
        class="toolbar-btn primary" 
        @click="emit('save')"
        :disabled="!canSave"
        :title="t('editorToolbar.saveRule')"
      >
        <span class="btn-icon">💾</span>
        <span class="btn-text">{{ t('editorToolbar.save') }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Rule } from '@/types/rule'
import { useResponsive } from '@/utils/useResponsive'

const { t } = useI18n()

const props = defineProps<{
  rule: Rule | null
  canSave: boolean
}>()

const emit = defineEmits<{
  (e: 'save'): void
  (e: 'clear'): void
  (e: 'export'): void
  (e: 'import'): void
}>()

const { isTablet, isMobile } = useResponsive()

const nodeCount = computed(() => {
  return props.rule?.graph.nodes.length || 0
})

const edgeCount = computed(() => {
  return props.rule?.graph.edges.length || 0
})

const showStats = computed(() => !isMobile.value)
</script>

<style scoped>
.editor-toolbar {
  height: 56px;
  background: var(--toolbar-bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: var(--toolbar-shadow);
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--toolbar-text);
  white-space: nowrap;
}

.toolbar-center {
  display: flex;
  align-items: center;
}

.stats {
  display: flex;
  gap: 20px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--toolbar-stat-text);
  font-size: 14px;
}

.stat-label {
  color: var(--toolbar-stat-label);
}

.stat-value {
  font-weight: 600;
  color: var(--color-primary);
}

.toolbar-right {
  display: flex;
  gap: 10px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--toolbar-btn-bg);
  color: var(--toolbar-text);
  -webkit-user-select: none;
  user-select: none;
}

.toolbar-btn:hover {
  background: var(--toolbar-btn-hover-bg);
  transform: translateY(-1px);
}

.toolbar-btn:active {
  transform: scale(0.98);
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.toolbar-btn.primary {
  background: var(--color-primary);
}

.toolbar-btn.primary:hover {
  background: var(--color-primary-hover);
}

.toolbar-btn.danger {
  background: var(--color-danger);
}

.toolbar-btn.danger:hover {
  background: var(--color-danger-hover, #c0392b);
}

.btn-icon {
  font-size: 14px;
}

.btn-text {
  white-space: nowrap;
}

.tablet-toolbar {
  padding: 0 16px;
}

.tablet-toolbar .toolbar-title {
  font-size: 16px;
}

.tablet-toolbar .toolbar-btn {
  padding: 10px 14px;
  font-size: 14px;
  min-height: 40px;
}

.tablet-toolbar .btn-icon {
  font-size: 16px;
}

.mobile-toolbar {
  height: 50px;
  padding: 0 12px;
}

.mobile-toolbar .toolbar-title {
  font-size: 14px;
}

.mobile-toolbar .toolbar-right {
  gap: 8px;
}

.mobile-toolbar .toolbar-btn {
  padding: 8px 12px;
  font-size: 13px;
  min-height: 36px;
}

.mobile-toolbar .btn-text {
  display: none;
}

.mobile-toolbar .btn-icon {
  font-size: 18px;
}

@media (max-width: 1024px) {
  .editor-toolbar {
    height: 52px;
    padding: 0 16px;
  }
  
  .toolbar-title {
    font-size: 16px;
  }
  
  .stats {
    gap: 16px;
  }
  
  .stat-item {
    font-size: 13px;
  }
  
  .toolbar-btn {
    padding: 10px 14px;
    font-size: 14px;
    min-height: 40px;
  }
}

@media (max-width: 768px) {
  .editor-toolbar {
    height: 50px;
    padding: 0 12px;
  }
  
  .toolbar-title {
    font-size: 14px;
  }
  
  .toolbar-right {
    gap: 8px;
  }
  
  .toolbar-btn {
    padding: 8px 12px;
    font-size: 13px;
    min-height: 44px;
    min-width: 44px;
  }
  
  .btn-text {
    display: none;
  }
  
  .btn-icon {
    font-size: 18px;
  }
}

@media (hover: none) and (pointer: coarse) {
  .toolbar-btn:hover {
    transform: none;
  }
  
  .toolbar-btn:active {
    transform: scale(0.98);
  }
}
</style>
