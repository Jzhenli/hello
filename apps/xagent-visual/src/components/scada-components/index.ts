// 统一导出所有 SCADA 组件、注册工具和类型定义

// 导出公共类型
export type {
  ComponentType,
  StyleConfig,
  ComponentTemplate,
  ComponentMetadata
} from './types'

// 导出各组件配置类型和元数据
export type { GaugeConfig } from './gauge/metadata'
export type { ChartConfig } from './chart/metadata'
export type { IndicatorConfig } from './indicator/metadata'
export type { SwitchConfig } from './switch/metadata'
export type { SliderConfig } from './slider/metadata'
export type { TextConfig } from './text/metadata'
export type { ButtonConfig } from './button/metadata'

// 聚合所有组件模板
import { gaugeMetadata } from './gauge/metadata'
import { chartLineMetadata, chartBarMetadata } from './chart/metadata'
import { indicatorMetadata } from './indicator/metadata'
import { switchMetadata } from './switch/metadata'
import { sliderMetadata } from './slider/metadata'
import { textMetadata } from './text/metadata'
import { imageMetadata } from './image/metadata'
import { buttonMetadata } from './button/metadata'
import { containerMetadata } from './container/metadata'

export const COMPONENT_TEMPLATES = [
  gaugeMetadata.template,
  chartLineMetadata.template,
  chartBarMetadata.template,
  indicatorMetadata.template,
  switchMetadata.template,
  sliderMetadata.template,
  textMetadata.template,
  imageMetadata.template,
  buttonMetadata.template,
  containerMetadata.template,
]

// 导出注册工具
export { componentRegistry, getComponent, registerComponent, getRegisteredTypes } from './registry'

// 导出组件（按需使用）
export { default as ScadaGauge } from './gauge/index.vue'
export { default as ScadaChart } from './chart/index.vue'
export { default as ScadaIndicator } from './indicator/index.vue'
export { default as ScadaSwitch } from './switch/index.vue'
export { default as ScadaSlider } from './slider/index.vue'
export { default as ScadaText } from './text/index.vue'
export { default as ScadaImage } from './image/index.vue'
export { default as ScadaButton } from './button/index.vue'
export { default as ScadaContainer } from './container/index.vue'
