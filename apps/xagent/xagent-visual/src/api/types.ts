export type DeviceStatus = 'active' | 'inactive' | 'maintenance' | 'error'
export type StandardDataType = 'bool' | 'int' | 'float' | 'string'
export type PluginType = 'south' | 'north' | 'filter' | 'rule' | 'delivery'

export interface PluginReference {
  name: string
  config: Record<string, unknown>
}

export interface PointConfig {
  name: string
  description?: string
  data_type: string
  standard_data_type?: StandardDataType
  unit?: string
  enabled: boolean
  config: Record<string, unknown>
  metadata?: Record<string, unknown>
  tags?: string[]
}

export interface DeviceConfig {
  asset: string
  name?: string
  description?: string
  enabled: boolean
  status?: DeviceStatus
  plugin: PluginReference
  points: PointConfig[]
  metadata?: Record<string, unknown>
  tags?: string[]
  created_at?: string
  updated_at?: string
}

export interface DeviceCreateResponse {
  success: boolean
  message: string
  asset: string
  plugin_id?: string
  requires_reload: boolean
}

export interface DeviceUpdateResponse {
  success: boolean
  message: string
  asset: string
  updated_fields: string[]
}

export interface PointCreateResponse {
  success: boolean
  message: string
  asset: string
  point_name: string
  requires_reload: boolean
}

export interface DeviceListResponse {
  count: number
  devices: DeviceConfig[]
}

export interface BatchOperationResult {
  total: number
  succeeded: number
  failed: number
  details: Record<string, unknown>[]
}

export interface DeviceReloadResponse {
  success: boolean
  message: string
  asset?: string
  reload_status?: string
}

export interface PluginConfig {
  name: string
  type: PluginType
  version: string
  description?: string
  enabled: boolean
  defaults: Record<string, unknown>
  capabilities: string[]
}

export interface PointWithValue extends PointConfig {
  currentValue?: number | boolean | string
  lastUpdate?: string
  quality?: 'good' | 'bad' | 'uncertain'
}

export interface RulePluginConfig {
  name: string
  config: Record<string, any>
}

export interface RuleDataSubscription {
  asset: string
  point: string
  mode?: 'single' | 'window'
  window_size?: number
  window_type?: 'sliding' | 'tumbling'
  aggregation?: 'none' | 'avg' | 'sum' | 'min' | 'max'
  min_data_points?: number
  max_data_points?: number
}

export interface RuleNotificationConfig {
  title?: string
  message?: string
  level?: 'info' | 'warning' | 'error' | 'critical'
  threshold?: number | string
  recipients?: string[]
}

export interface RuleResponse {
  id: string
  name: string
  description?: string
  enabled: boolean
  plugin: RulePluginConfig
  data_subscriptions?: RuleDataSubscription[]
  notification?: RuleNotificationConfig
  pipeline_id?: string
  channel_ids?: string[]
  execution_count?: number
  last_triggered?: number
}

export interface RuleListResponse {
  count: number
  rules: RuleResponse[]
}

export interface RuleCreateRequest {
  id: string
  name: string
  description?: string
  enabled: boolean
  plugin: RulePluginConfig
  data_subscriptions?: RuleDataSubscription[]
  notification?: RuleNotificationConfig
  pipeline_id?: string
  channel_ids?: string[]
}

export interface RuleUpdateRequest {
  name?: string
  description?: string
  enabled?: boolean
  plugin?: RulePluginConfig
  data_subscriptions?: RuleDataSubscription[]
  notification?: RuleNotificationConfig
  pipeline_id?: string
  channel_ids?: string[]
}

export interface RuleOperationResponse {
  success: boolean
  message: string
  rule_id?: string
}

export interface RuleEngineStatusResponse {
  running: boolean
  loaded_rules: number
  registered_channels: number
  active_pipelines: number
  aggregation_subscriptions: number
  event_bus_connected: boolean
}
