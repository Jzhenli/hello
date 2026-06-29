export type ComponentType = 
  | 'gauge' 
  | 'chart-line'
  | 'chart-bar'
  | 'indicator'
  | 'switch'
  | 'slider'
  | 'text'
  | 'image'
  | 'button'
  | 'container'

export interface PointBinding {
  deviceId: string
  pointName: string
  pointDescription?: string
  unit?: string
}

export interface StyleConfig {
  width: number
  height: number
  backgroundColor?: string
  borderColor?: string
  borderWidth?: number
  borderRadius?: number
  fontSize?: number
  fontColor?: string
  opacity?: number
}

export interface GaugeConfig {
  min: number
  max: number
  unit: string
  thresholds: { value: number; color: string }[]
  showValue: boolean
}

export interface ChartConfig {
  timeRange: '1h' | '6h' | '24h' | '7d'
  lineColor: string
  areaFill: boolean
  showLegend: boolean
}

export interface IndicatorConfig {
  onColor: string
  offColor: string
  blinkOnAlarm: boolean
}

export interface SwitchConfig {
  onText: string
  offText: string
  confirmRequired: boolean
  writePoint: PointBinding | null
}

export interface TextConfig {
  content: string
  fontSize: number
  fontColor: string
  fontWeight: 'normal' | 'bold'
  textAlign: 'left' | 'center' | 'right'
}

export interface ButtonConfig {
  text: string
  type: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  writeValue: number | boolean | string
  writePoint: PointBinding | null
}

export interface ScadaComponent {
  id: string
  type: ComponentType
  name: string
  x: number
  y: number
  style: StyleConfig
  binding: PointBinding | null
  gaugeConfig?: GaugeConfig
  chartConfig?: ChartConfig
  indicatorConfig?: IndicatorConfig
  switchConfig?: SwitchConfig
  textConfig?: TextConfig
  buttonConfig?: ButtonConfig
  locked: boolean
  visible: boolean
}

export type PanelType = 'Dashboard' | 'Graphic'

export interface ScadaPanel {
  id: string
  name: string
  type: PanelType
  description?: string
  width: number
  height: number
  grid: number
  backgroundColor: string
  backgroundImage?: string
  components: ScadaComponent[]
  createdAt: number
  updatedAt: number
}

export interface ComponentTemplate {
  type: ComponentType
  name: string
  icon: string
  category: string
  defaultStyle: StyleConfig
  defaultConfig: Record<string, any>
}

export const COMPONENT_TEMPLATES: ComponentTemplate[] = [
  {
    type: 'gauge',
    name: 'scadaComponentNames.gauge',
    icon: '🎯',
    category: 'scadaComponentCategories.gauge',
    defaultStyle: { width: 150, height: 150 },
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
  },
  {
    type: 'chart-line',
    name: 'scadaComponentNames.chartLine',
    icon: '📈',
    category: 'scadaComponentCategories.chart',
    defaultStyle: { width: 300, height: 200 },
    defaultConfig: {
      chartConfig: {
        timeRange: '24h',
        lineColor: '#3498db',
        areaFill: true,
        showLegend: true
      }
    }
  },
  {
    type: 'chart-bar',
    name: 'scadaComponentNames.chartBar',
    icon: '📊',
    category: 'scadaComponentCategories.chart',
    defaultStyle: { width: 300, height: 200 },
    defaultConfig: {
      chartConfig: {
        timeRange: '24h',
        lineColor: '#27ae60',
        areaFill: false,
        showLegend: true
      }
    }
  },
  {
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
  },
  {
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
  },
  {
    type: 'slider',
    name: 'scadaComponentNames.slider',
    icon: '🎚️',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {}
  },
  {
    type: 'text',
    name: 'scadaComponentNames.text',
    icon: '📝',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 150, height: 40, fontSize: 14, fontColor: '#2c3e50' },
    defaultConfig: {
      textConfig: {
        content: '文本标签',
        fontSize: 14,
        fontColor: '#2c3e50',
        fontWeight: 'normal',
        textAlign: 'center'
      }
    }
  },
  {
    type: 'image',
    name: 'scadaComponentNames.image',
    icon: '🖼️',
    category: 'scadaComponentCategories.basic',
    defaultStyle: { width: 200, height: 150 },
    defaultConfig: {}
  },
  {
    type: 'button',
    name: 'scadaComponentNames.button',
    icon: '🔲',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 100, height: 40 },
    defaultConfig: {
      buttonConfig: {
        text: '执行',
        type: 'primary',
        writeValue: true,
        writePoint: null
      }
    }
  },
  {
    type: 'container',
    name: 'scadaComponentNames.container',
    icon: '📦',
    category: 'scadaComponentCategories.layout',
    defaultStyle: { width: 300, height: 200, backgroundColor: '#f5f7fa', borderWidth: 1, borderColor: '#dce1e6' },
    defaultConfig: {}
  }
]
