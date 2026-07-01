import type { StyleConfig, ScadaComponentMeta } from '../types'
import ScadaIndicator from './index.vue'
import IndicatorConfigPanel from './ConfigPanel.vue'

export interface IndicatorConfig {
  onColor: string
  offColor: string
  blinkOnAlarm: boolean
}

export const indicatorMeta: ScadaComponentMeta = {
  type: 'indicator',
  component: ScadaIndicator,
  configPanel: IndicatorConfigPanel,
  template: {
    name: 'scadaComponentNames.indicator',
    icon: '💡',
    category: 'scadaComponentCategories.indicator',
    defaultStyle: { width: 60, height: 60 },
    defaultConfig: {
      indicatorConfig: {
        onColor: '#27ae60',
        offColor: '#95a5a6',
        blinkOnAlarm: true
      }
    }
  },
  configTypes: {
    IndicatorConfig: null as unknown as IndicatorConfig
  }
}
