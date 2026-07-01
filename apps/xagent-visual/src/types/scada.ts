// 核心数据类型定义
// 组件相关类型已迁移至 @/components/scada-components/
// 此处重新导出以保持向后兼容

// 重新导出组件公共类型
export type {
  ComponentType,
  StyleConfig,
  ComponentTemplate
} from '@/components/scada-components/types'

// 重新导出各组件配置类型
export type { GaugeConfig } from '@/components/scada-components/gauge/metadata'
export type { ChartConfig } from '@/components/scada-components/chart/metadata'
export type { IndicatorConfig } from '@/components/scada-components/indicator/metadata'
export type { SwitchConfig } from '@/components/scada-components/switch/metadata'
export type { SliderConfig } from '@/components/scada-components/slider/metadata'
export type { TextConfig } from '@/components/scada-components/text/metadata'
export type { ButtonConfig } from '@/components/scada-components/button/metadata'

// 重新导出组件模板列表
export { COMPONENT_TEMPLATES } from '@/components/scada-components'

export interface PointBinding {
  deviceId: string
  pointName: string
  pointDescription?: string
  unit?: string
}

export interface ScadaComponent {
  id: string
  type: import('@/components/scada-components/types').ComponentType
  name: string
  x: number
  y: number
  style: import('@/components/scada-components/types').StyleConfig
  binding: PointBinding | null
  gaugeConfig?: import('@/components/scada-components/gauge/metadata').GaugeConfig
  chartConfig?: import('@/components/scada-components/chart/metadata').ChartConfig
  indicatorConfig?: import('@/components/scada-components/indicator/metadata').IndicatorConfig
  switchConfig?: import('@/components/scada-components/switch/metadata').SwitchConfig
  sliderConfig?: import('@/components/scada-components/slider/metadata').SliderConfig
  textConfig?: import('@/components/scada-components/text/metadata').TextConfig
  imageConfig?: { url?: string; fit?: string }
  buttonConfig?: import('@/components/scada-components/button/metadata').ButtonConfig
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
