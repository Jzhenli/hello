import type { Component } from 'vue'
import type { ComponentType } from './types'

// 导入所有 SCADA 组件
import ScadaGauge from './gauge/index.vue'
import ScadaChart from './chart/index.vue'
import ScadaIndicator from './indicator/index.vue'
import ScadaSwitch from './switch/index.vue'
import ScadaSlider from './slider/index.vue'
import ScadaText from './text/index.vue'
import ScadaImage from './image/index.vue'
import ScadaButton from './button/index.vue'
import ScadaContainer from './container/index.vue'

// 组件注册表：type -> 组件映射
export const componentRegistry: Record<string, Component> = {
  'gauge': ScadaGauge,
  'chart-line': ScadaChart,
  'chart-bar': ScadaChart,
  'indicator': ScadaIndicator,
  'switch': ScadaSwitch,
  'slider': ScadaSlider,
  'text': ScadaText,
  'image': ScadaImage,
  'button': ScadaButton,
  'container': ScadaContainer,
}

/**
 * 获取组件实例
 * @param type 组件类型
 * @returns 组件构造函数或 undefined
 */
export function getComponent(type: ComponentType): Component | undefined {
  return componentRegistry[type]
}

/**
 * 注册新组件（支持运行时动态注册）
 * @param type 组件类型
 * @param component 组件构造函数
 */
export function registerComponent(type: ComponentType, component: Component) {
  componentRegistry[type] = component
}

/**
 * 获取所有已注册的组件类型
 */
export function getRegisteredTypes(): ComponentType[] {
  return Object.keys(componentRegistry) as ComponentType[]
}
