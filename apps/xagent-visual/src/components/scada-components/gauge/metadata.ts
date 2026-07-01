import type { ComponentMetadata, StyleConfig } from '../types'

export interface GaugeConfig {
  min: number
  max: number
  unit: string
  thresholds: { value: number; color: string }[]
  showValue: boolean
}

const defaultStyle: StyleConfig = { width: 150, height: 150 }

export const gaugeMetadata: ComponentMetadata = {
  template: {
    type: 'gauge',
    name: 'scadaComponentNames.gauge',
    icon: '🎯',
    category: 'scadaComponentCategories.gauge',
    defaultStyle,
    defaultConfig: {
      gaugeConfig: {
        min: 0,
        max: 100,
        unit: '',
        thresholds: [
          { value: 30, color: '#27ae60' },
          { value: 70, color: '#f39c12' },
          { value: 100, color: '#e74c3c' }
        ],
        showValue: true
      }
    }
  }
}
