import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { SliderConfig } from '../../registry'
import ScadaSlider from './index.vue'

export const sliderMeta: ScadaComponentMeta = {
  type: 'slider',
  component: ScadaSlider,
  template: {
    name: 'scadaComponentNames.slider',
    icon: '🎚️',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {
      sliderConfig: { min: 0, max: 100, step: 1 }
    }
  },
  configTypes: {
    SliderConfig: null as unknown as SliderConfig
  }
}
