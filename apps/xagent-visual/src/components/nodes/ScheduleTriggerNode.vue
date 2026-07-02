<template>
  <div class="rule-node schedule-trigger">
    <Handle type="target" :position="Position.Top" />
    
    <div class="node-header">
      <span class="node-icon">⏰</span>
      <span class="node-title">{{ node.data?.label || t('nodeViews.scheduleTrigger') }}</span>
    </div>
    
    <div class="node-body">
      <div class="node-info has-data">
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.mode') }}:</span>
          <span class="info-value">
            {{ scheduleData?.mode === 'cron' ? 'Cron' : (scheduleData?.mode === 'once' ? t('nodeViews.once') : t('nodeViews.periodic')) }}
          </span>
        </div>
        <div class="info-row">
          <span class="info-label">{{ t('nodeViews.time') }}:</span>
          <span class="info-value">{{ getScheduleDisplay }}</span>
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

const scheduleData = computed(() => node.data?.scheduleTrigger)

const getScheduleDisplay = computed(() => {
  if (!scheduleData.value) return t('nodeViews.notConfigured')
  
  if (scheduleData.value.mode === 'cron') {
    return scheduleData.value.cron || t('nodeViews.cronExpression')
  }
  
  if (scheduleData.value.mode === 'once') {
    return `${t('nodeViews.once')}: ${scheduleData.value.time}`
  }
  
  const freqMap: Record<string, string> = {
    daily: t('nodeViews.daily'),
    weekly: t('nodeViews.weekly'),
    monthly: t('nodeViews.monthly')
  }
  
  const freq = freqMap[scheduleData.value.frequency || 'daily']
  return `${freq} ${scheduleData.value.time}`
})
</script>

<style scoped>
.schedule-trigger {
  background: var(--node-schedule-bg);
  border: 2px solid var(--node-schedule-border);
}
</style>
