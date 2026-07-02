<template>
  <div class="config-section">
    <div class="section-title">{{ t('componentConfig.indicatorConfig') }}</div>
    <div class="form-group">
      <label>{{ t('componentConfig.onColor') }}</label>
      <input type="color" :value="component.indicatorConfig?.onColor ?? '#27ae60'" @input="updateConfig('onColor', ($event.target as HTMLInputElement).value)">
    </div>
    <div class="form-group">
      <label>{{ t('componentConfig.offColor') }}</label>
      <input type="color" :value="component.indicatorConfig?.offColor ?? '#95a5a6'" @input="updateConfig('offColor', ($event.target as HTMLInputElement).value)">
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
  const config = props.component.indicatorConfig || { onColor: '#27ae60', offColor: '#95a5a6', blinkOnAlarm: true }
  scadaStore.updateComponent(props.component.id, {
    indicatorConfig: { ...config, [key]: value }
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
</style>