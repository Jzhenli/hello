import type { StyleConfig, ScadaComponentMeta } from '../types'
import type { PointBinding } from '@/types/scada'
import ScadaButton from './index.vue'

export interface ButtonConfig {
  text: string
  type: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  writeValue: number | boolean | string
  writePoint: PointBinding | null
}

export const buttonMeta: ScadaComponentMeta = {
  type: 'button',
  component: ScadaButton,
  template: {
    name: 'scadaComponentNames.button',
    icon: '🔲',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 100, height: 40 },
    defaultConfig: {
      buttonConfig: {
        text: '执行',
        type: 'primary',
        writeValue: true,
        writePoint: null
      }
    }
  },
  configTypes: {
    ButtonConfig: null as unknown as ButtonConfig
  }
}
