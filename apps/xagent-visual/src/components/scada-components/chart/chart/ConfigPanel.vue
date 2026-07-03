<template>
  <div class="config-section">
    <div class="section-title">{{ t('componentConfig.chartConfig') }}</div>
    <div class="form-group">
      <label>{{ t('componentConfig.timeRange') }}</label>
      <select :value="component.chartConfig?.timeRange ?? '24h'" @change="updateConfig('timeRange', ($event.target as HTMLSelectElement).value)">
        <option value="1h">{{ t('dashboard.timeRange1h') }}</option>
        <option value="6h">{{ t('pointTrend.timeRange6h') }}</option>
        <option value="24h">{{ t('dashboard.timeRange24h') }}</option>
        <option value="7d">{{ t('dashboard.timeRange7d') }}</option>
      </select>
    </div>
    <div class="form-group">
      <label>{{ t('componentConfig.lineColor') }}</label>
      <input type="color" :value="component.chartConfig?.lineColor ?? '#3498db'" @input="updateConfig('lineColor', ($event.target as HTMLInputElement).value)">
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import type { ScadaComponent } from '@/types/scada'

const { t } = useI18n()
const scadaStore = useScadaStore()

const props = defineProps<{
  component: ScadaComponent
}>()

const updateConfig = (key: string, value: any) => {
  const config = props.component.chartConfig || { timeRange: '24h', lineColor: '#3498db', areaFill: true, showLegend: true }
  scadaStore.updateComponent(props.component.id, {
    chartConfig: { ...config, [key]: value }
  })
}
</script>

<style scoped>
.config-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}

.config-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  font-size: 13px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}
</style>