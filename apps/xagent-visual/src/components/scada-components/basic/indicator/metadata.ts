import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { IndicatorConfig } from '../../registry'
import ScadaIndicator from './index.vue'
import IndicatorConfigPanel from './ConfigPanel.vue'

export const indicatorMeta: ScadaComponentMeta = {
  type: 'indicator',
  component: ScadaIndicator,
  configPanel: IndicatorConfigPanel,
  template: {
    name: 'scadaComponentNames.indicator',
    icon: '💡',
    category: 'scadaComponentCategories.basic',
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
