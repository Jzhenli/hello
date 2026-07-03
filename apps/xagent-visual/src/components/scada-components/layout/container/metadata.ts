import type { StyleConfig, ScadaComponentMeta } from '../../types'
import ScadaContainer from './index.vue'

export const containerMeta: ScadaComponentMeta = {
  type: 'container',
  component: ScadaContainer,
  template: {
    name: 'scadaComponentNames.container',
    icon: '📦',
    category: 'scadaComponentCategories.layout',
    defaultStyle: { width: 300, height: 200, backgroundColor: '#f5f7fa', borderWidth: 1, borderColor: '#dce1e6' },
    defaultConfig: {}
  }
}
