import type { ComponentMetadata } from '../types'

export interface TextConfig {
  content: string
  fontSize: number
  fontColor: string
  fontWeight: 'normal' | 'bold'
  textAlign: 'left' | 'center' | 'right'
}

export const textMetadata: ComponentMetadata = {
  template: {
    type: 'text',
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
  }
}
