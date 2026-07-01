import type { StyleConfig, ScadaComponentMeta } from '../types'
import type { PointBinding } from '@/types/scada'
import ScadaSwitch from './index.vue'

export interface SwitchConfig {
  onText: string
  offText: string
  confirmRequired: boolean
  writePoint: PointBinding | null
}

export const switchMeta: ScadaComponentMeta = {
  type: 'switch',
  component: ScadaSwitch,
  template: {
    name: 'scadaComponentNames.switch',
    icon: '🔘',
    category: 'scadaComponentCategories.control',
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
