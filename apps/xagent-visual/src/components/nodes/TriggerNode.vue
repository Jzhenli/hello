<template>
  <div class="rule-node trigger-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">🎯</span>
      <span class="node-title">{{ t('nodeViews.trigger') }}</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.triggerSource') }}:</span>
          <span class="info-value">{{ nodeData?.source || '-' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.triggerField') }}:</span>
          <span class="info-value">{{ nodeData?.field || '-' }}</span>
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

const nodeData = computed(() => node.data?.trigger)
const hasValidData = computed(() => 
  nodeData.value?.source && nodeData.value?.field
)
</script>

<style scoped>
.trigger-node {
  background: var(--node-trigger-bg);
  border: 2px solid var(--node-trigger-border);
}
</style>
