import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { GaugeConfig } from '../../registry'
import ScadaGauge from './index.vue'
import GaugeConfigPanel from './ConfigPanel.vue'

const defaultStyle: StyleConfig = { width: 150, height: 150 }

export const gaugeMeta: ScadaComponentMeta = {
  type: 'gauge',
  component: ScadaGauge,
  configPanel: GaugeConfigPanel,
  template: {
    name: 'scadaComponentNames.gauge',
    icon: '🎯',
    category: 'scadaComponentCategories.basic',
    defaultStyle,
    defaultConfig: {
      gaugeConfig: {
        min: 0,
        max: 100,
        unit: '',
        thresholds: [
          { value: 30, color: '#27ae60' },
          { value: 70, color: '#f39c12' },
          { value: 100, color: '#e74c3c' }
        ],
        showValue: true
      }
    }
  },
  configTypes: {
    GaugeConfig: null as unknown as GaugeConfig
  }
}
