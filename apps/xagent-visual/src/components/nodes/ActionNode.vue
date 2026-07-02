<template>
  <div class="rule-node action-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⚡</span>
      <span class="node-title">{{ t('nodeViews.action') }}</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.target') }}:</span>
          <span class="info-value">{{ nodeData?.target_asset || '-' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.operation') }}:</span>
          <span class="info-value">{{ nodeData?.operation || '-' }}</span>
        </div>
        <div class="delay-badge" v-if="nodeData?.delay">
          {{ delayText }}
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

const nodeData = computed(() => node.data?.action)
const hasValidData = computed(() => 
  nodeData.value?.target_asset && nodeData.value?.operation
)

const delayText = computed(() => {
  const delay = nodeData.value?.delay || 0
  if (delay === 0) return t('nodeViews.instant')
  if (delay < 60) return `${t('nodeViews.delay')} ${delay}${t('nodeViews.seconds')}`
  if (delay < 3600) return `${t('nodeViews.delay')} ${Math.floor(delay / 60)}${t('nodeViews.minutes')}`
  return `${t('nodeViews.delay')} ${Math.floor(delay / 3600)}${t('nodeViews.hours')}`
})
</script>

<style scoped>
.action-node {
  background: var(--node-action-bg);
  border: 2px solid var(--node-action-border);
}

.delay-badge {
  margin-top: 6px;
  padding: 2px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  font-size: 11px;
  color: var(--text-white);
}
</style>
