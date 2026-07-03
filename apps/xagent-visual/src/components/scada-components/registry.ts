import type { Component } from 'vue'
import type { ScadaComponentMeta, PointBinding } from './types'

// ─── 组件配置接口定义 ──────────────────────────────────────────
// 集中定义所有组件的配置类型，新增组件时在此添加对应接口

/** 仪表盘配置 */
export interface GaugeConfig {
  min: number
  max: number
  unit: string
  thresholds: { value: number; color: string }[]
  showValue: boolean
}

/** 图表配置 */
export interface ChartConfig {
  timeRange: '1h' | '6h' | '24h' | '7d'
  lineColor: string
  areaFill: boolean
  showLegend: boolean
}

/** 指示灯配置 */
export interface IndicatorConfig {
  onColor: string
  offColor: string
  blinkOnAlarm: boolean
}

/** 开关配置 */
export interface SwitchConfig {
  onText: string
  offText: string
  confirmRequired: boolean
  writePoint: PointBinding | null
}

/** 滑块配置 */
export interface SliderConfig {
  min: number
  max: number
  step: number
}

/** 文本配置 */
export interface TextConfig {
  content: string
  fontSize: number
  fontColor: string
  fontWeight: 'normal' | 'bold'
  textAlign: 'left' | 'center' | 'right'
}

/** 按钮配置 */
export interface ButtonConfig {
  text: string
  type: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  writeValue: number | boolean | string
  writePoint: PointBinding | null
}

// ─── 导入所有组件元数据 ────────────────────────────────────────
import { gaugeMeta } from './basic/gauge/metadata'
import { chartLineMeta, chartBarMeta } from './chart/chart/metadata'
import { indicatorMeta } from './basic/indicator/metadata'
import { switchMeta } from './basic/switch/metadata'
import { sliderMeta } from './basic/slider/metadata'
import { textMeta } from './layout/text/metadata'
import { imageMeta } from './basic/image/metadata'
import { buttonMeta } from './basic/button/metadata'
import { containerMeta } from './layout/container/metadata'

// ─── 统一组件注册表：type -> 完整元数据 ─────────────────────────
// 新增组件只需在此添加映射，ComponentType 自动推导
export const componentMetaRegistry = {
  gauge: gaugeMeta,
  'chart-line': chartLineMeta,
  'chart-bar': chartBarMeta,
  indicator: indicatorMeta,
  switch: switchMeta,
  slider: sliderMeta,
  text: textMeta,
  image: imageMeta,
  button: buttonMeta,
  container: containerMeta,
} as const

/** 组件类型 —— 从注册表键名自动推导 */
export type ComponentType = keyof typeof componentMetaRegistry

/** 注册表记录类型，用于动态访问场景 */
type Registry = Record<string, ScadaComponentMeta>

// ─── 查询 API ──────────────────────────────────────────────────

/** 获取组件完整元数据 */
export const getComponentMeta = (type: ComponentType): ScadaComponentMeta | undefined =>
  componentMetaRegistry[type]

/** 获取组件视图 */
export const getComponent = (type: ComponentType): Component | undefined =>
  componentMetaRegistry[type]?.component

/** 获取组件配置面板（无则返回 null） */
export const getConfigPanel = (type: string): Component | null =>
  (componentMetaRegistry as Registry)[type]?.configPanel ?? null

/** 获取组件模板（用于拖拽创建），type 非法时返回 undefined */
export const getComponentTemplate = (type: ComponentType) => {
  const meta = componentMetaRegistry[type]
  return meta && { type: meta.type, ...meta.template }
}

/** 获取所有组件模板列表（用于组件库面板） */
export const getAllTemplates = () =>
  Object.values(componentMetaRegistry).map(({ type, template }) => ({ type, ...template }))

/** 组件模板列表（数组形式，向后兼容） */
export const COMPONENT_TEMPLATES = getAllTemplates()

// ─── 注册 API ──────────────────────────────────────────────────

/**
 * 注册新组件（支持运行时动态注册）
 * @throws 当 meta 缺少 type 或 component 时抛出异常
 */
export const registerComponent = (meta: ScadaComponentMeta): void => {
  if (!meta?.type) {
    throw new Error('[registerComponent] meta.type is required')
  }
  if (!meta.component) {
    throw new Error(`[registerComponent] meta.component is required for type "${meta.type}"`)
  }
  ;(componentMetaRegistry as Registry)[meta.type] = meta
}

/** 获取所有已注册的组件类型 */
export const getRegisteredTypes = (): ComponentType[] =>
  Object.keys(componentMetaRegistry) as ComponentType[]
