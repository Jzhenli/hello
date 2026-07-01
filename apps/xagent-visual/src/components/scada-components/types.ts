// SCADA 组件公共类型定义

// 组件类型联合 - 新增组件在此添加类型
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

// 组件模板接口
export interface ComponentTemplate {
  type: ComponentType
  name: string
  icon: string
  category: string
  defaultStyle: StyleConfig
  defaultConfig: Record<string, any>
}

// 组件元数据接口
export interface ComponentMetadata {
  template: ComponentTemplate
  configTypes?: Record<string, any>
}
