<template>
  <div class="rule-node notification-node">
    <Handle type="target" :position="Position.Top" />

    <div class="node-header">
      <span class="node-icon">📢</span>
      <span class="node-title">{{ t('nodeViews.notification') }}</span>
      <span class="level-badge" :style="{ background: levelColor }">{{ nodeData?.level || 'warning' }}</span>
    </div>

    <div class="node-body">
      <div class="node-info">
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.channel') }}:</span>
          <span class="info-value">{{ channelLabel }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.level') }}:</span>
          <span class="info-value">{{ levelLabel }}</span>
        </div>
      </div>
    </div>

    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position, useNode } from '@vue-flow/core'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RuleNodeData } from '@/types/rule'

const { t } = useI18n()
const { node } = useNode<RuleNodeData>()

const nodeData = computed(() => node.data?.notification)

const channelLabel = computed(() => {
  if (nodeData.value?.channel_type === 'system') return '🔔 ' + t('ruleNodes.systemNotification')
  if (nodeData.value?.channel_type === 'email') return '📧 ' + t('ruleNodes.email')
  if (nodeData.value?.channel_type === 'webhook') return '🔗 ' + t('ruleNodes.webhook')
  return t('nodeViews.notConfigured')
})

const levelLabel = computed(() => {
  const level = nodeData.value?.level || 'warning'
  const labels: Record<string, string> = {
    info: '💡 ' + t('ruleNodes.levelInfo'),
    warning: '⚠️ ' + t('ruleNodes.levelWarning'),
    error: '🔴 ' + t('ruleNodes.levelError'),
    critical: '🚨 ' + t('ruleNodes.levelCritical')
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

<style scoped>
.notification-node {
  background: var(--node-notification-bg);
  border: 2px solid var(--node-notification-border);
}

.level-badge {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 10px;
  color: var(--text-white);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
