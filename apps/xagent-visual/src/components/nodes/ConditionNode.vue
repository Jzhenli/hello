<script setup lang="ts">
import { Handle, Position, useNode } from '@vue-flow/core'
import { computed } from 'vue'
import type { RuleNodeData } from '@/types/rule'

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
  if (duration === 0) return '即时'
  if (duration < 60) return `${duration}秒`
  if (duration < 3600) return `${Math.floor(duration / 60)}分钟`
  return `${Math.floor(duration / 3600)}小时`
})
</script>

<template>
  <div class="rule-node condition-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⚙️</span>
      <span class="node-title">条件判断</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="condition-expression">
          <span class="field">{{ nodeData?.field || '字段' }}</span>
          <span class="operator">{{ operatorSymbol }}</span>
          <span class="value">{{ nodeData?.value || '值' }}</span>
        </div>
        <div class="duration-badge" v-if="nodeData?.duration">
          持续: {{ durationText }}
        </div>
      </div>
    </div>
    
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.condition-node {
  background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
  border: 2px solid #8e44ad;
}

.condition-expression {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}

.condition-expression .field {
  color: #fff;
  font-weight: 600;
}

.condition-expression .operator {
  color: #f1c40f;
  font-weight: bold;
}

.condition-expression .value {
  color: #2ecc71;
  font-weight: 600;
}

.duration-badge {
  margin-top: 6px;
  padding: 2px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  font-size: 11px;
  color: #ecf0f1;
}
</style>
