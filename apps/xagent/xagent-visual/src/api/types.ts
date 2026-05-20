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
