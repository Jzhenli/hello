import type { ComponentMetadata } from '../types'

export interface SliderConfig {
  min: number
  max: number
  step: number
}

export const sliderMetadata: ComponentMetadata = {
  template: {
    type: 'slider',
    name: 'scadaComponentNames.slider',
    icon: '🎚️',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {
      sliderConfig: { min: 0, max: 100, step: 1 }
    }
  }
}
