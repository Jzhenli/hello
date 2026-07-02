// 统一导出所有 SCADA 组件、注册工具和类型定义

// 导出公共类型
export type {
  StyleConfig,
  ScadaComponentMeta
} from './types'
export type { ComponentType } from './registry'

// 导出各组件配置类型（统一从 registry 导出）
export type {
  GaugeConfig,
  ChartConfig,
  IndicatorConfig,
  SwitchConfig,
  SliderConfig,
  TextConfig,
  ButtonConfig
} from './registry'

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
