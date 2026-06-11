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

export interface AlertResponse {
  id: string
  rule_id: string
  rule_name: string
  title: string
  message: string
  level: string
  status: string
  asset: string
  point_name: string
  current_value: string
  threshold: string
  triggered_at: number | null
  triggered_at_str: string
  metadata: Record<string, any>
}

export interface AlertListResponse {
  count: number
  alerts: AlertResponse[]
}

export type NorthChannelStatus = 'online' | 'offline' | 'error' | 'unknown'
export type NorthChannelProtocol = 'mqtt' | 'xnc' | 'http' | 'custom'

export interface MQTTConnectionConfig {
  broker: string
  port: number
  username?: string
  password?: string
  client_id: string
  topic: string
  command_topic?: string
  publish_mode?: 'single' | 'batch'
  command_timeout?: number
  qos: 0 | 1 | 2
  keepalive: number
  clean_session?: boolean
  will_topic?: string
  will_message?: string
  will_qos?: 0 | 1 | 2
  will_retain?: boolean
}

export interface XNCConnectionConfig {
  local_port: number
  protocol: 'protobuf' | 'json'
  remote_host: string
  remote_port: number
  reconnect_interval?: number
  mapping_config?: Record<string, unknown>
}

export interface HTTPConnectionConfig {
  endpoint: string
  method: 'GET' | 'POST' | 'PUT'
  headers?: Record<string, string>
  timeout?: number
  username?: string
  password?: string
}

export interface NorthChannelConnection {
  // MQTT字段
  broker?: string
  client_id?: string
  topic?: string
  command_topic?: string
  publish_mode?: 'single' | 'batch'
  command_timeout?: number
  qos?: 0 | 1 | 2
  keepalive?: number
  clean_session?: boolean
  will_topic?: string
  will_message?: string
  will_qos?: 0 | 1 | 2
  will_retain?: boolean
  
  // XNC字段
  local_port?: number
  protocol?: 'protobuf' | 'json'
  remote_host?: string
  remote_port?: number
  reconnect_interval?: number
  
  // HTTP字段
  endpoint?: string
  method?: 'GET' | 'POST' | 'PUT'
  headers?: Record<string, string>
  timeout?: number
  
  // 通用字段
  port?: number
  username?: string
  password?: string
}

export interface NorthChannelAdapter {
  type: string
  adapter?: string
  adapter_config?: Record<string, unknown>
  mapping_config?: Record<string, unknown>
  headers?: Record<string, string>
  config?: Record<string, unknown>
}

export interface NorthChannelUploadStrategy {
  immediate_upload: boolean
  batch_size: number
  interval: number
  retry_times: number
  retry_interval?: number
}

export interface NorthChannelStatistics {
  upload_rate: number
  success_rate: number
  backlog_count: number
  last_upload_time: string
  total_uploaded: number
  total_failed: number
  connection_uptime: number
}

export interface NorthChannelConfig {
  id: string
  name: string
  description?: string
  enabled: boolean
  protocol: NorthChannelProtocol
  status: NorthChannelStatus
  
  connection: NorthChannelConnection
  adapter: NorthChannelAdapter
  upload_strategy: NorthChannelUploadStrategy
  
  statistics?: NorthChannelStatistics
  
  tags?: string[]
  created_at?: string
  updated_at?: string
}

export interface NorthChannelCreateResponse {
  success: boolean
  message: string
  channel_id: string
  requires_restart: boolean
}

export interface NorthChannelUpdateResponse {
  success: boolean
  message: string
  channel_id: string
  updated_fields: string[]
}

export interface NorthChannelListResponse {
  count: number
  channels: NorthChannelConfig[]
}

export interface ConnectionTestRequest {
  channel_id?: string
  connection: NorthChannelConnection
  protocol: NorthChannelProtocol
}

export interface ConnectionTestResponse {
  success: boolean
  message: string
  latency?: number
  details?: Record<string, unknown>
}

export interface NorthChannelLog {
  id: string
  channel_id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'debug'
  message: string
  details?: Record<string, unknown>
}

export interface NorthChannelLogListResponse {
  count: number
  logs: NorthChannelLog[]
}

export interface SystemStatsResponse {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  uptime: number
  total_readings: number
  today_readings: number
  connection_count: number
  process_count: number
  load_average: number[]
}

export interface DataCollectionStats {
  time: string
  count: number
  timestamp: number
}

export interface DataCollectionStatsResponse {
  stats: DataCollectionStats[]
  total_count: number
  avg_rate: number
}

export interface DataQualityStats {
  good: number
  bad: number
  uncertain: number
  total: number
  quality_rate: number
}
