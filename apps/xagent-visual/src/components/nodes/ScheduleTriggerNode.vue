<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { RuleNodeData } from '@/types/rule'

const props = defineProps<{
  id: string
  data: RuleNodeData
  selected?: boolean
}>()

const scheduleData = props.data.scheduleTrigger

const getScheduleDisplay = () => {
  if (!scheduleData) return '未配置'
  
  if (scheduleData.mode === 'cron') {
    return scheduleData.cron || 'Cron表达式'
  }
  
  if (scheduleData.mode === 'once') {
    return `一次性: ${scheduleData.time}`
  }
  
  const freqMap: Record<string, string> = {
    daily: '每天',
    weekly: '每周',
    monthly: '每月'
  }
  
  const freq = freqMap[scheduleData.frequency || 'daily']
  return `${freq} ${scheduleData.time}`
}
</script>

<template>
  <div class="rule-node schedule-trigger" :class="{ selected }">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⏰</span>
      <span class="node-title">{{ data.label || '定时触发器' }}</span>
    </div>
    
    <div class="node-body">
      <div class="node-info has-data">
        <div class="info-row">
          <span class="info-label">模式:</span>
          <span class="info-value">{{ scheduleData?.mode === 'cron' ? 'Cron' : (scheduleData?.mode === 'once' ? '一次性' : '周期性') }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">时间:</span>
          <span class="info-value">{{ getScheduleDisplay() }}</span>
        </div>
      </div>
    </div>
    
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.rule-node {
  background: linear-gradient(135deg, #00bcd4 0%, #0097a7 100%);
  color: #fff;
}

.schedule-trigger {
  background: linear-gradient(135deg, #00bcd4 0%, #0097a7 100%);
}
</style>
