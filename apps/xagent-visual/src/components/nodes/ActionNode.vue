<script setup lang="ts">
import { Handle, Position, useNode } from '@vue-flow/core'
import { computed } from 'vue'
import type { RuleNodeData } from '@/types/rule'

const { node } = useNode<RuleNodeData>()

const nodeData = computed(() => node.data?.action)
const hasValidData = computed(() => 
  nodeData.value?.target_asset && nodeData.value?.operation
)

const delayText = computed(() => {
  const delay = nodeData.value?.delay || 0
  if (delay === 0) return '立即执行'
  if (delay < 60) return `延迟 ${delay}秒`
  if (delay < 3600) return `延迟 ${Math.floor(delay / 60)}分钟`
  return `延迟 ${Math.floor(delay / 3600)}小时`
})
</script>

<template>
  <div class="rule-node action-node">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⚡</span>
      <span class="node-title">执行动作</span>
    </div>
    
    <div class="node-body">
      <div class="node-info" :class="{ 'has-data': hasValidData }">
        <div class="info-row">
          <span class="info-label">目标:</span>
          <span class="info-value">{{ nodeData?.target_asset || '-' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">操作:</span>
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

<style scoped>
.action-node {
  background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
  border: 2px solid #229954;
}

.delay-badge {
  margin-top: 6px;
  padding: 2px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  font-size: 11px;
  color: #ecf0f1;
}
</style>
