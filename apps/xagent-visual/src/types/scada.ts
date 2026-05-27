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

export interface ScadaPanel {
  id: string
  name: string
  description?: string
  width: number
  height: number
  grid: number
  backgroundColor: string
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
    name: '仪表盘',
    icon: '🎯',
    category: '仪表',
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
    name: '折线图',
    icon: '📈',
    category: '图表',
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
    name: '柱状图',
    icon: '📊',
    category: '图表',
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
    name: '指示灯',
    icon: '💡',
    category: '指示',
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
    name: '开关',
    icon: '🔘',
    category: '控制',
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
    name: '滑块',
    icon: '🎚️',
    category: '控制',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {}
  },
  {
    type: 'text',
    name: '文本',
    icon: '📝',
    category: '基础',
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
    name: '图片',
    icon: '🖼️',
    category: '基础',
    defaultStyle: { width: 200, height: 150 },
    defaultConfig: {}
  },
  {
    type: 'button',
    name: '按钮',
    icon: '🔲',
    category: '控制',
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
    name: '容器',
    icon: '📦',
    category: '布局',
    defaultStyle: { width: 300, height: 200, backgroundColor: '#f5f7fa', borderWidth: 1, borderColor: '#dce1e6' },
    defaultConfig: {}
  }
]
