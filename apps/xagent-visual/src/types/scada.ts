// 核心数据类型定义
// 组件相关类型已迁移至 @/components/scada-components/
// 此处重新导出以保持向后兼容

// 重新导出组件公共类型
export type { StyleConfig, PointBinding, ComponentTemplate } from '@/components/scada-components/types'

// ComponentType 从 registry 导出（自动推导）
export type { ComponentType } from '@/components/scada-components/registry'

// 导入公共类型和组件配置类型
import type { StyleConfig, PointBinding } from '@/components/scada-components/types'
import type { ComponentType,
  GaugeConfig,
  ChartConfig,
  IndicatorConfig,
  SwitchConfig,
  SliderConfig,
  TextConfig,
  ButtonConfig
} from '@/components/scada-components/registry'

export type {
  GaugeConfig,
  ChartConfig,
  IndicatorConfig,
  SwitchConfig,
  SliderConfig,
  TextConfig,
  ButtonConfig
}

// 重新导出组件模板列表
export { COMPONENT_TEMPLATES } from '@/components/scada-components'

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
  sliderConfig?: SliderConfig
  textConfig?: TextConfig
  imageConfig?: { url?: string; fit?: string }
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
