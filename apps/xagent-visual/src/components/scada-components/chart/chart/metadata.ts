import type { StyleConfig, ScadaComponentMeta } from '../../types'
import type { ChartConfig } from '../../registry'
import ScadaChart from './index.vue'
import ChartConfigPanel from './ConfigPanel.vue'

const defaultStyle: StyleConfig = { width: 300, height: 200 }

export const chartLineMeta: ScadaComponentMeta = {
  type: 'chart-line',
  component: ScadaChart,
  configPanel: ChartConfigPanel,
  template: {
    name: 'scadaComponentNames.chartLine',
    icon: '📈',
    category: 'scadaComponentCategories.chart',
    defaultStyle,
    defaultConfig: {
      chartConfig: {
        timeRange: '24h',
        lineColor: '#3498db',
        areaFill: true,
        showLegend: true
      }
    }
  },
  configTypes: {
    ChartConfig: null as unknown as ChartConfig
  }
}

export const chartBarMeta: ScadaComponentMeta = {
  type: 'chart-bar',
  component: ScadaChart,
  configPanel: ChartConfigPanel,
  template: {
    name: 'scadaComponentNames.chartBar',
    icon: '📊',
    category: 'scadaComponentCategories.chart',
    defaultStyle,
    defaultConfig: {
      chartConfig: {
        timeRange: '24h',
        lineColor: '#27ae60',
        areaFill: false,
        showLegend: true
      }
    }
  },
  configTypes: {
    ChartConfig: null as unknown as ChartConfig
  }
}
