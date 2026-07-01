import type { ComponentMetadata } from '../types'
import type { PointBinding } from '@/types/scada'

export interface SwitchConfig {
  onText: string
  offText: string
  confirmRequired: boolean
  writePoint: PointBinding | null
}

export const switchMetadata: ComponentMetadata = {
  template: {
    type: 'switch',
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
  }
}
