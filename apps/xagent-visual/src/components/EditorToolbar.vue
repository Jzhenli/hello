<script setup lang="ts">
import { computed } from 'vue'
import type { Rule } from '@/types/rule'
import { useResponsive } from '@/utils/useResponsive'

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

<template>
  <div class="editor-toolbar" :class="{ 'mobile-toolbar': isMobile, 'tablet-toolbar': isTablet }">
    <div class="toolbar-left">
      <h2 class="toolbar-title">场景联动规则编辑器</h2>
    </div>
    
    <div v-if="showStats" class="toolbar-center">
      <div class="stats">
        <span class="stat-item">
          <span class="stat-label">节点:</span>
          <span class="stat-value">{{ nodeCount }}</span>
        </span>
        <span class="stat-item">
          <span class="stat-label">连线:</span>
          <span class="stat-value">{{ edgeCount }}</span>
        </span>
      </div>
    </div>
    
    <div class="toolbar-right">
      <button class="toolbar-btn" @click="emit('import')" title="导入规则">
        <span class="btn-icon">📥</span>
        <span class="btn-text">导入</span>
      </button>
      <button class="toolbar-btn" @click="emit('export')" title="导出规则">
        <span class="btn-icon">📤</span>
        <span class="btn-text">导出</span>
      </button>
      <button class="toolbar-btn danger" @click="emit('clear')" title="清空画布">
        <span class="btn-icon">🗑️</span>
        <span class="btn-text">清空</span>
      </button>
      <button 
        class="toolbar-btn primary" 
        @click="emit('save')"
        :disabled="!canSave"
        title="保存规则"
      >
        <span class="btn-icon">💾</span>
        <span class="btn-text">保存</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.editor-toolbar {
  height: 56px;
  background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
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
  color: #ecf0f1;
  font-size: 14px;
}

.stat-label {
  color: #bdc3c7;
}

.stat-value {
  font-weight: 600;
  color: #3498db;
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
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  -webkit-user-select: none;
  user-select: none;
}

.toolbar-btn:hover {
  background: rgba(255, 255, 255, 0.2);
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
  background: #3498db;
}

.toolbar-btn.primary:hover {
  background: #2980b9;
}

.toolbar-btn.danger {
  background: #e74c3c;
}

.toolbar-btn.danger:hover {
  background: #c0392b;
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
