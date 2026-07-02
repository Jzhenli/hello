<template>
  <div class="rule-node condition-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⚙️</span>
      <span class="node-title">{{ t('nodeViews.condition') }}</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="condition-expression">
          <span class="field">{{ nodeData?.field || t('nodeViews.triggerField') }}</span>
          <span class="operator">{{ operatorSymbol }}</span>
          <span class="value">{{ nodeData?.value || t('ruleNodes.conditionValue') }}</span>
        </div>
        <div class="duration-badge" v-if="nodeData?.duration">
          {{ t('nodeViews.duration') }}: {{ durationText }}
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

const nodeData = computed(() => node.data?.condition)
const hasValidData = computed(() => 
  nodeData.value?.field && nodeData.value?.value
)

const operatorSymbol = computed(() => {
  const op = nodeData.value?.operator
  const symbols: Record<string, string> = {
    '>': '>',
    '<': '<',
    '>=': '≥',
    '<=': '≤',
    '==': '=',
    '!=': '≠',
    'regex': '=~'
  }
  return symbols[op || ''] || op
})

const durationText = computed(() => {
  const duration = nodeData.value?.duration || 0
  if (duration === 0) return t('nodeViews.instant')
  if (duration < 60) return `${duration}${t('nodeViews.seconds')}`
  if (duration < 3600) return `${Math.floor(duration / 60)}${t('nodeViews.minutes')}`
  return `${Math.floor(duration / 3600)}${t('nodeViews.hours')}`
})
</script>

<style scoped>
.condition-node {
  background: var(--node-condition-bg);
  border: 2px solid var(--node-condition-border);
}

.condition-expression {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}

.condition-expression .field {
  color: var(--text-white);
  font-weight: 600;
}

.condition-expression .operator {
  color: var(--color-warning);
  font-weight: bold;
}

.condition-expression .value {
  color: var(--color-success);
  font-weight: 600;
}

.duration-badge {
  margin-top: 6px;
  padding: 2px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  font-size: 11px;
  color: var(--text-white);
}
</style>
