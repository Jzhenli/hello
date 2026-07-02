<template>
  <div class="config-section">
    <div class="section-title">{{ t('componentConfig.gaugeConfig') }}</div>
    <div class="form-row">
      <div class="form-group">
        <label>{{ t('componentConfig.minValue') }}</label>
        <input type="number" :value="component.gaugeConfig?.min ?? 0" @input="updateConfig('min', +($event.target as HTMLInputElement).value)">
      </div>
      <div class="form-group">
        <label>{{ t('componentConfig.maxValue') }}</label>
        <input type="number" :value="component.gaugeConfig?.max ?? 100" @input="updateConfig('max', +($event.target as HTMLInputElement).value)">
      </div>
    </div>
    <div class="form-group">
      <label>{{ t('componentConfig.unit') }}</label>
      <input type="text" :value="component.gaugeConfig?.unit ?? ''" @input="updateConfig('unit', ($event.target as HTMLInputElement).value)">
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
  const config = props.component.gaugeConfig || { min: 0, max: 100, unit: '', thresholds: [], showValue: true }
  scadaStore.updateComponent(props.component.id, {
    gaugeConfig: { ...config, [key]: value }
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

.form-group input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  font-size: 13px;
}

.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-row {
  display: flex;
  gap: 8px;
}

.form-row .form-group {
  flex: 1;
}
</style>