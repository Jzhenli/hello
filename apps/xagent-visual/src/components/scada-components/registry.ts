import type { Component } from 'vue'
import type { ComponentType, ScadaComponentMeta } from './types'

// 导入所有组件元数据（每个组件的视图、配置面板、模板信息已整合）
import { gaugeMeta } from './gauge/metadata'
import { chartLineMeta, chartBarMeta } from './chart/metadata'
import { indicatorMeta } from './indicator/metadata'
import { switchMeta } from './switch/metadata'
import { sliderMeta } from './slider/metadata'
import { textMeta } from './text/metadata'
import { imageMeta } from './image/metadata'
import { buttonMeta } from './button/metadata'
import { containerMeta } from './container/metadata'

// 统一组件注册表：type -> 完整元数据
export const componentMetaRegistry: Record<string, ScadaComponentMeta> = {
  'gauge': gaugeMeta,
  'chart-line': chartLineMeta,
  'chart-bar': chartBarMeta,
  'indicator': indicatorMeta,
  'switch': switchMeta,
  'slider': sliderMeta,
  'text': textMeta,
  'image': imageMeta,
  'button': buttonMeta,
  'container': containerMeta,
}

/**
 * 获取组件完整元数据
 * @param type 组件类型
 * @returns 组件元数据或 undefined
 */
export function getComponentMeta(type: ComponentType): ScadaComponentMeta | undefined {
  return componentMetaRegistry[type]
}

/**
 * 获取组件视图
 * @param type 组件类型
 * @returns 组件构造函数或 undefined
 */
export function getComponent(type: ComponentType): Component | undefined {
  return componentMetaRegistry[type]?.component
}

/**
 * 获取组件配置面板
 * @param type 组件类型
 * @returns 配置面板组件或 null
 */
export function getConfigPanel(type: string): Component | null {
  return componentMetaRegistry[type]?.configPanel ?? null
}

/**
 * 获取组件模板（用于拖拽创建）
 * @param type 组件类型
 * @returns 组件模板或 undefined
 */
export function getComponentTemplate(type: ComponentType) {
  const meta = componentMetaRegistry[type]
  return meta ? { type: meta.type, ...meta.template } : undefined
}

/**
 * 获取所有组件模板列表（用于组件库面板）
 */
export function getAllTemplates() {
  return Object.values(componentMetaRegistry).map(meta => ({
    type: meta.type,
    ...meta.template
  }))
}

/**
 * 组件模板列表（数组形式，向后兼容）
 */
export const COMPONENT_TEMPLATES = getAllTemplates()

/**
 * 注册新组件（支持运行时动态注册，整合视图和配置面板）
 * @param meta 组件完整元数据
 */
export function registerComponent(meta: ScadaComponentMeta) {
  componentMetaRegistry[meta.type] = meta
}

/**
 * 获取所有已注册的组件类型
 */
export function getRegisteredTypes(): ComponentType[] {
  return Object.keys(componentMetaRegistry) as ComponentType[]
}
