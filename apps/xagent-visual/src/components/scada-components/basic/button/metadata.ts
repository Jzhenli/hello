import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { ButtonConfig } from '../../registry'
import ScadaButton from './index.vue'

export const buttonMeta: ScadaComponentMeta = {
  type: 'button',
  component: ScadaButton,
  template: {
    name: 'scadaComponentNames.button',
    icon: '🔲',
    category: 'scadaComponentCategories.basic',
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
