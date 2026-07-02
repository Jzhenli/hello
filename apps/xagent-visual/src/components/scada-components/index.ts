// 统一导出所有 SCADA 组件、注册工具和类型定义

// 导出公共类型
export type {
  StyleConfig,
  ScadaComponentMeta
} from './types'
export type { ComponentType } from './registry'

// 导出各组件配置类型和元数据
export type { GaugeConfig } from './gauge/metadata'
export type { ChartConfig } from './chart/metadata'
export type { IndicatorConfig } from './indicator/metadata'
export type { SwitchConfig } from './switch/metadata'
export type { SliderConfig } from './slider/metadata'
export type { TextConfig } from './text/metadata'
export type { ButtonConfig } from './button/metadata'

// 导出统一注册表
export {
  componentMetaRegistry,
  getComponentMeta,
  getComponent,
  getConfigPanel,
  getComponentTemplate,
  getAllTemplates,
  COMPONENT_TEMPLATES,
  registerComponent,
  getRegisteredTypes
} from './registry'
