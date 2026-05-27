<script setup lang="ts">
import { Handle, Position, useNode } from '@vue-flow/core'
import { computed } from 'vue'
import type { RuleNodeData } from '@/types/rule'

const { node } = useNode<RuleNodeData>()

const nodeData = computed(() => node.data?.logic)

const operatorLabel = computed(() => {
  const op = nodeData.value?.operator
  const labels: Record<string, string> = {
    'and': 'AND',
    'or': 'OR',
    'not': 'NOT'
  }
  return labels[op || 'and'] || 'AND'
})

const operatorColor = computed(() => {
  const op = nodeData.value?.operator
  const colors: Record<string, string> = {
    'and': '#3498db',
    'or': '#e67e22',
    'not': '#e74c3c'
  }
  return colors[op || 'and'] || '#3498db'
})
</script>

<template>
  <div class="rule-node logic-node">
    <Handle type="target" :position="Position.Top" />
    <Handle type="target" :position="Position.Left" id="left" />
    
    <div class="node-header">
      <span class="node-icon">🔀</span>
      <span class="node-title">逻辑运算</span>
    </div>
    
    <div class="node-body">
      <div class="logic-operator" :style="{ color: operatorColor }">
        {{ operatorLabel }}
      </div>
    </div>
    
    <Handle type="source" :position="Position.Bottom" />
    <Handle type="target" :position="Position.Right" id="right" />
  </div>
</template>

<style scoped>
.logic-node {
  background: linear-gradient(135deg, #e67e22 0%, #d35400 100%);
  border: 2px solid #d35400;
  min-width: 120px;
}

.logic-operator {
  font-size: 18px;
  font-weight: bold;
  text-align: center;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
</style>
