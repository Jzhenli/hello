import type { ComponentMetadata, StyleConfig } from '../types'

export interface ChartConfig {
  timeRange: '1h' | '6h' | '24h' | '7d'
  lineColor: string
  areaFill: boolean
  showLegend: boolean
}

const defaultStyle: StyleConfig = { width: 300, height: 200 }

export const chartLineMetadata: ComponentMetadata = {
  template: {
    type: 'chart-line',
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
  }
}

export const chartBarMetadata: ComponentMetadata = {
  template: {
    type: 'chart-bar',
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
  }
}
