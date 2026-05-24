<script setup lang="ts">
import { Handle, Position, useNode } from '@vue-flow/core'
import { computed } from 'vue'
import type { RuleNodeData } from '@/types/rule'

const { node } = useNode<RuleNodeData>()

const nodeData = computed(() => node.data?.trigger)
const hasValidData = computed(() => 
  nodeData.value?.source && nodeData.value?.field
)
</script>

<template>
  <div class="rule-node trigger-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">🎯</span>
      <span class="node-title">触发器</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="info-row">
          <span class="info-label">数据源:</span>
          <span class="info-value">{{ nodeData?.source || '-' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">字段:</span>
          <span class="info-value">{{ nodeData?.field || '-' }}</span>
        </div>
      </div>
    </div>
    
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.trigger-node {
  background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
  border: 2px solid #2980b9;
}
</style>
