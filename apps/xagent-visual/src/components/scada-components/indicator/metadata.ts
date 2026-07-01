import type { ComponentMetadata } from '../types'

export interface IndicatorConfig {
  onColor: string
  offColor: string
  blinkOnAlarm: boolean
}

export const indicatorMetadata: ComponentMetadata = {
  template: {
    type: 'indicator',
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
  }
}
