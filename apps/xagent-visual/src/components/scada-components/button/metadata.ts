import type { ComponentMetadata } from '../types'
import type { PointBinding } from '@/types/scada'

export interface ButtonConfig {
  text: string
  type: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  writeValue: number | boolean | string
  writePoint: PointBinding | null
}

export const buttonMetadata: ComponentMetadata = {
  template: {
    type: 'button',
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
  }
}
