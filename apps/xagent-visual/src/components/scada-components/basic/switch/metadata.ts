import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { SwitchConfig } from '../../registry'
import ScadaSwitch from './index.vue'

export const switchMeta: ScadaComponentMeta = {
  type: 'switch',
  component: ScadaSwitch,
  template: {
    name: 'scadaComponentNames.switch',
    icon: '🔘',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 100, height: 50 },
    defaultConfig: {
      switchConfig: {
        onText: '开',
        offText: '关',
        confirmRequired: true,
        writePoint: null
      }
    }
  },
  configTypes: {
    SwitchConfig: null as unknown as SwitchConfig
  }
}
