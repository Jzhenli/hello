import type { StyleConfig, ScadaComponentMeta } from '../../types'
import ScadaImage from './index.vue'
import ImageConfigPanel from './ConfigPanel.vue'

export const imageMeta: ScadaComponentMeta = {
  type: 'image',
  component: ScadaImage,
  configPanel: ImageConfigPanel,
  template: {
    name: 'scadaComponentNames.image',
    icon: '🖼️',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 200, height: 150 },
    defaultConfig: {}
  }
}
