import type { Component } from 'vue'

// 组件样式配置
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

/**
 * 统一组件注册元数据
 * 整合组件视图、配置面板、模板信息、类型定义
 */
export interface ScadaComponentMeta {
  /** 组件类型标识 */
  type: string
  /** 组件视图 */
  component: Component
  /** 配置面板组件（可选，无则使用默认） */
  configPanel?: Component | null
  /** 组件模板信息（用于拖拽创建） */
  template: {
    name: string
    icon: string
    category: string
    defaultStyle: StyleConfig
    defaultConfig: Record<string, any>
  }
  /** 配置类型定义（可选） */
  configTypes?: Record<string, any>
}
