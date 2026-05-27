<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import type { RuleNodeData } from '@/types/rule'

const props = defineProps<{
  id: string
  data: RuleNodeData
  selected?: boolean
}>()

const nodeData = computed(() => props.data.notification)

const channelLabel = computed(() => {
  if (nodeData.value?.channel_type === 'system') return '🔔 系统通知'
  if (nodeData.value?.channel_type === 'email') return '📧 邮件'
  if (nodeData.value?.channel_type === 'webhook') return '🔗 Webhook'
  return '未配置'
})

const levelLabel = computed(() => {
  const level = nodeData.value?.level || 'warning'
  const labels: Record<string, string> = {
    info: '💡 提示',
    warning: '⚠️ 警告',
    error: '🔴 错误',
    critical: '🚨 紧急'
  }
  return labels[level] || level
})

const levelColor = computed(() => {
  const level = nodeData.value?.level || 'warning'
  const colors: Record<string, string> = {
    info: '#3b82f6',
    warning: '#f59e0b',
    error: '#ef4444',
    critical: '#dc2626'
  }
  return colors[level] || '#f59e0b'
})
</script>

<template>
  <div class="rule-node notification-node">
    <Handle type="target" :position="Position.Top" />

    <div class="node-header">
      <span class="node-icon">📢</span>
      <span class="node-title">通知告警</span>
      <span class="level-badge" :style="{ background: levelColor }">{{ nodeData?.level || 'warning' }}</span>
    </div>

    <div class="node-body">
      <div class="node-info">
        <div class="info-row">
          <span class="info-label">渠道:</span>
          <span class="info-value">{{ channelLabel }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">级别:</span>
          <span class="info-value">{{ levelLabel }}</span>
        </div>
      </div>
    </div>

    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.notification-node {
  background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
  border: 2px solid #c0392b;
}

.level-badge {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10px;
  color: #fff;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>