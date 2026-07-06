<template>
  <el-card class="project-card" shadow="hover">
    <div class="project-info">
      <div class="project-title-row">
        <h3 class="project-name">{{ panel.name }}</h3>
        <el-tag :type="panel.type === 'Dashboard' ? 'info' : 'warning'" size="small" class="type-tag">
          {{ panel.type === 'Dashboard' ? $t('scada.dashboardType') : $t('scada.graphicType') }}
        </el-tag>
        <el-button
          type="success"
          :icon="View"
          size="small"
          circle
          @click="$emit('preview', panel)"
          class="preview-btn"
        />
      </div>
      <p class="project-desc">{{ panel.description || $t('scada.noDescription') }}</p>
      <div class="project-meta">
        <span>{{ $t('scada.componentCount') }}: {{ panel.components?.length || 0 }}</span>
        <span>{{ $t('scada.createTime') }}: {{ formatTime(panel.createdAt) }}</span>
      </div>
    </div>
    <div class="project-actions">
      <el-button
        type="primary"
        :icon="Edit"
        size="small"
        @click="$emit('edit', panel)"
      >
        {{ $t('scada.edit') }}
      </el-button>
      <el-button
        type="warning"
        :icon="Setting"
        size="small"
        @click="$emit('settings', panel)"
      >
        {{ $t('scada.settings') }}
      </el-button>
      <el-button
        type="danger"
        :icon="Delete"
        size="small"
        @click="$emit('delete', panel.id)"
      >
        {{ $t('scada.delete') }}
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Edit, Delete, Setting, View } from '@element-plus/icons-vue'

defineProps<{
  panel: any
  formatTime: (timestamp: number) => string
}>()

defineEmits<{
  (e: 'preview', panel: any): void
  (e: 'edit', panel: any): void
  (e: 'settings', panel: any): void
  (e: 'delete', id: string): void
}>()
</script>

<style scoped>
.project-card {
  transition: all 0.3s;
}

.project-info {
  margin-bottom: 16px;
}

.project-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.project-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.type-tag {
  flex-shrink: 0;
}

.preview-btn {
  margin-left: auto;
  flex-shrink: 0;
}

.project-desc {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.project-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.project-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}
</style>
