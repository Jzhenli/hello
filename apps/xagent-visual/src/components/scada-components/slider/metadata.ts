import type { StyleConfig, ScadaComponentMeta } from '../types'
import ScadaSlider from './index.vue'

export interface SliderConfig {
  min: number
  max: number
  step: number
}

export const sliderMeta: ScadaComponentMeta = {
  type: 'slider',
  component: ScadaSlider,
  template: {
    name: 'scadaComponentNames.slider',
    icon: '🎚️',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {
      sliderConfig: { min: 0, max: 100, step: 1 }
    }
  },
  configTypes: {
    SliderConfig: null as unknown as SliderConfig
  }
}
