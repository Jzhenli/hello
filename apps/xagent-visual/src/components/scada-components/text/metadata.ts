import type { StyleConfig, ScadaComponentMeta } from '../types'
import ScadaText from './index.vue'

export interface TextConfig {
  content: string
  fontSize: number
  fontColor: string
  fontWeight: 'normal' | 'bold'
  textAlign: 'left' | 'center' | 'right'
}

export const textMeta: ScadaComponentMeta = {
  type: 'text',
  component: ScadaText,
  template: {
    name: 'scadaComponentNames.text',
    icon: '📝',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 150, height: 40, fontSize: 14, fontColor: '#2c3e50' },
    defaultConfig: {
      textConfig: {
        content: '文本标签',
        fontSize: 14,
        fontColor: '#2c3e50',
        fontWeight: 'normal',
        textAlign: 'center'
      }
    }
  },
  configTypes: {
    TextConfig: null as unknown as TextConfig
  }
}
