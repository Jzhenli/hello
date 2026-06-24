<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDeviceStore } from '@/stores/devices'
import { usePointStore } from '@/stores/points'
import { useUserStore } from '@/stores/users'
import type { DeviceConfig, PointConfig, StandardDataType } from '@/api/types'
import type { DeviceListItem } from '@/stores/devices'
import { useResponsive } from '@/utils/useResponsive'
import yaml from 'js-yaml'
import { 
  Plus, 
  Upload, 
  Download, 
  Refresh,
  CircleCheck,
  CircleClose,
  Search,
  TrendCharts,
  Delete,
  Edit,
  MoreFilled,
  RefreshRight
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PointTrend from '@/components/PointTrend.vue'

const { t } = useI18n()

const deviceStore = useDeviceStore()
const pointStore = usePointStore()
const userStore = useUserStore()
const { isTouch, isTablet, isMobile, width } = useResponsive()

const searchQuery = ref('')
const statusFilter = ref('')
const selectedDeviceAsset = ref<string | null>(null)
const showTrend = ref(false)
const selectedPointForTrend = ref<{ deviceAsset: string; pointName: string } | null>(null)

const activeTab = ref('devices')

const isCompactMode = computed(() => isTablet.value || isMobile.value || width.value <= 1024)

const filteredSouthDevices = computed(() => {
  let list = deviceStore.southDevices
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    list = list.filter(d =>
      d.name.toLowerCase().includes(query) ||
      d.asset.toLowerCase().includes(query) ||
      d.pluginName.toLowerCase().includes(query)
    )
  }
  if (statusFilter.value === 'online') {
    list = list.filter(d => d.status === 'active' && d.enabled)
  } else if (statusFilter.value === 'offline') {
    list = list.filter(d => d.status !== 'active' || !d.enabled)
  }
  return list
})

const handleSearch = () => {}

const handleFilterChange = () => {}

const handleToggleDevice = async (asset: string) => {
  try {
    await deviceStore.toggleDevice(asset)
    ElMessage.success(t('devices.status_toggled'))
  } catch (e: unknown) {
    ElMessage.error(t('devices.operation_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
  }
}

const handleRefresh = async () => {
  await deviceStore.fetchDevices()
  await deviceStore.fetchConnectionStatus()
  await pointStore.fetchDevicesWithPoints()
}

const showDeviceDialog = ref(false)
const deviceForm = ref({
  asset: '',
  name: '',
  description: '',
  enabled: true,
  pluginName: 'modbus_tcp',
  host: '',
  port: 502,
  slave_id: 1,
  timeout: 5,
  gateway_ip: '',
  local_ip: '',
  connection_type: 'automatic',
  interval: 1,
  sync_mode: 'smart',
  sync_interval: 60,
  device_id: 1234,
  tags: ''
})
const deviceFormRef = ref()
const isEditing = ref(false)
const editingAsset = ref('')
const saving = ref(false)

const pluginOptions = [
  { 
    label: t('devices.protocol.modbus_tcp'), 
    value: 'modbus_tcp', 
    defaultPort: 502,
    defaultConfig: { slave_id: 1, timeout: 5, interval: 1 }
  },
  { 
    label: t('devices.protocol.modbus_rtu'), 
    value: 'modbus_rtu', 
    defaultPort: 0,
    defaultConfig: { slave_id: 1, timeout: 5, interval: 1 }
  },
  { 
    label: t('devices.protocol.knx'), 
    value: 'knx', 
    defaultPort: 3671,
    defaultConfig: { 
      local_ip: '', 
      timeout: 5, 
      connection_type: 'automatic',
      interval: 1,
      sync_mode: 'smart',
      sync_interval: 60
    }
  },
  { 
    label: t('devices.protocol.bacnet'), 
    value: 'bacnet', 
    defaultPort: 47808,
    defaultConfig: { device_id: 1234, timeout: 5, interval: 1 }
  }
]

const deviceFormRules = {
  asset: [{ required: true, message: t('devices.asset_required'), trigger: 'blur' }],
  pluginName: [{ required: true, message: t('devices.plugin_required'), trigger: 'change' }],
  host: [{ required: true, message: t('devices.host_required'), trigger: 'blur' }]
}

const handlePluginChange = (val: string) => {
  const opt = pluginOptions.find(o => o.value === val)
  if (opt) {
    deviceForm.value.port = opt.defaultPort
    if (opt.defaultConfig) {
      Object.assign(deviceForm.value, opt.defaultConfig)
    }
  }
}

const handleAddDevice = () => {
  isEditing.value = false
  editingAsset.value = ''
  deviceForm.value = {
    asset: '',
    name: '',
    description: '',
    enabled: true,
    pluginName: 'modbus_tcp',
    host: '',
    port: 502,
    slave_id: 1,
    timeout: 5,
    gateway_ip: '',
    local_ip: '',
    connection_type: 'automatic',
    interval: 1,
    sync_mode: 'smart',
    sync_interval: 60,
    device_id: 1234,
    tags: ''
  }
  showDeviceDialog.value = true
}

const handleEditDevice = (device: DeviceListItem) => {
  isEditing.value = true
  editingAsset.value = device.asset
  deviceForm.value = {
    asset: device.asset,
    name: device.name,
    description: '',
    enabled: device.enabled,
    pluginName: device.pluginName,
    host: device.connection.host,
    port: device.connection.port,
    slave_id: (device.pluginConfig.slave_id as number) || 1,
    timeout: (device.pluginConfig.timeout as number) || 5,
    gateway_ip: (device.pluginConfig.gateway_ip as string) || '',
    local_ip: (device.pluginConfig.local_ip as string) || '',
    connection_type: (device.pluginConfig.connection_type as string) || 'automatic',
    interval: (device.pluginConfig.interval as number) || 1,
    sync_mode: (device.pluginConfig.sync_mode as string) || 'smart',
    sync_interval: (device.pluginConfig.sync_interval as number) || 60,
    device_id: (device.pluginConfig.device_id as number) || 1234,
    tags: device.tags.join(', ')
  }
  showDeviceDialog.value = true
}

const handleSaveDevice = async () => {
  if (!deviceFormRef.value) return
  try {
    await deviceFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const buildPluginConfig = (): Record<string, unknown> => {
      const baseConfig: Record<string, unknown> = {}
      
      if (deviceForm.value.pluginName === 'modbus_tcp' || deviceForm.value.pluginName === 'modbus_rtu') {
        baseConfig.host = deviceForm.value.host
        baseConfig.port = deviceForm.value.port
        baseConfig.slave_id = deviceForm.value.slave_id
        baseConfig.timeout = deviceForm.value.timeout
        baseConfig.interval = deviceForm.value.interval
      } else if (deviceForm.value.pluginName === 'knx') {
        baseConfig.gateway_ip = deviceForm.value.gateway_ip || deviceForm.value.host
        baseConfig.gateway_port = deviceForm.value.port
        if (deviceForm.value.local_ip) {
          baseConfig.local_ip = deviceForm.value.local_ip
        }
        if (deviceForm.value.connection_type) {
          baseConfig.connection_type = deviceForm.value.connection_type
        }
        baseConfig.interval = deviceForm.value.interval
        baseConfig.sync_mode = deviceForm.value.sync_mode
        baseConfig.sync_interval = deviceForm.value.sync_interval
        baseConfig.timeout = deviceForm.value.timeout
      } else if (deviceForm.value.pluginName === 'bacnet') {
        baseConfig.host = deviceForm.value.host
        baseConfig.port = deviceForm.value.port
        baseConfig.device_id = deviceForm.value.device_id
        baseConfig.timeout = deviceForm.value.timeout
        baseConfig.interval = deviceForm.value.interval
      }
      
      return baseConfig
    }

    const config = buildPluginConfig()

    if (isEditing.value) {
      await deviceStore.updateDevice(editingAsset.value, {
        name: deviceForm.value.name || deviceForm.value.asset,
        description: deviceForm.value.description,
        enabled: deviceForm.value.enabled,
        plugin: {
          name: deviceForm.value.pluginName,
          config
        },
        tags: deviceForm.value.tags ? deviceForm.value.tags.split(',').map(tag => tag.trim()).filter(Boolean) : []
      })
      ElMessage.success(t('devices.device_updated'))
    } else {
      const device: DeviceConfig = {
        asset: deviceForm.value.asset,
        name: deviceForm.value.name || deviceForm.value.asset,
        description: deviceForm.value.description || undefined,
        enabled: deviceForm.value.enabled,
        plugin: {
          name: deviceForm.value.pluginName,
          config
        },
        points: [],
        tags: deviceForm.value.tags ? deviceForm.value.tags.split(',').map(tag => tag.trim()).filter(Boolean) : []
      }
      await deviceStore.createDevice(device)
      ElMessage.success(t('devices.device_created'))
    }
    showDeviceDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : t('devices.unknown_error'))
    ElMessage.error(isEditing.value ? t('devices.update_failed', { detail }) : t('devices.create_failed', { detail }))
  } finally {
    saving.value = false
  }
}

const handleDeleteDevice = (device: DeviceListItem) => {
  ElMessageBox.confirm(
    t('devices.delete_device_confirm', { name: device.name, asset: device.asset }),
    t('devices.delete_confirm'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deviceStore.deleteDevice(device.asset)
      if (selectedDeviceAsset.value === device.asset) {
        selectedDeviceAsset.value = null
      }
      ElMessage.success(t('devices.device_deleted'))
    } catch (e: unknown) {
      ElMessage.error(t('devices.delete_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
    }
  }).catch(() => {})
}

const handleReloadDevice = async (asset: string) => {
  try {
    await deviceStore.reloadDevice(asset)
    ElMessage.success(t('devices.device_reloaded'))
  } catch (e: unknown) {
    ElMessage.error(t('devices.reload_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
  }
}

const handleViewPoints = async (asset: string) => {
  selectedDeviceAsset.value = asset
  await pointStore.fetchDevicePoints(asset)
}

const handleViewTrend = (deviceAsset: string, pointName: string) => {
  selectedPointForTrend.value = { deviceAsset, pointName }
  pointStore.selectPoint(deviceAsset, pointName)
  showTrend.value = true
}

const handleCloseTrend = () => {
  showTrend.value = false
  selectedPointForTrend.value = null
  pointStore.clearSelection()
}

const getDevicePoints = (asset: string) => {
  return pointStore.getDevicePoints(asset)
}

const showPointDialog = ref(false)
const pointForm = ref({
  name: '',
  description: '',
  data_type: 'uint16',
  standard_data_type: '' as StandardDataType | '',
  unit: '',
  enabled: true,
  configJson: '{}',
  metadataJson: '{}',
  tags: '',
  address: 0,
  register_type: 'holding' as 'holding' | 'input' | 'coil' | 'discrete_input',
  count: 1,
  scale: null as number | null,
  offset: null as number | null,
  byte_order: 'big' as 'big' | 'little',
  word_order: 'big' as 'big' | 'little',
  group_address: '',
  status_address: '',
  control_address: '',
  writable: false,
  object_type: 'analogInput' as string,
  object_instance: 0,
  property: 'presentValue' as string,
  alarm_high: null as number | null,
  alarm_low: null as number | null,
  min: null as number | null,
  max: null as number | null
})
const pointFormRef = ref()
const isEditingPoint = ref(false)
const editingPointName = ref('')
const savingPoint = ref(false)

const showWriteDialog = ref(false)
const writeForm = ref({
  deviceAsset: '',
  pointName: '',
  pointType: '' as 'analog' | 'digital' | '',
  unit: '',
  currentValue: '' as string,
  value: '' as string,
  boolValue: false
})
const writing = ref(false)

const currentDevicePluginName = computed(() => {
  if (!selectedDeviceAsset.value) return ''
  const device = deviceStore.getDeviceByAsset(selectedDeviceAsset.value)
  return device?.plugin?.name || ''
})

const modbusDataTypes = [
  { label: t('devices.datatype.uint16'), value: 'uint16' },
  { label: t('devices.datatype.int16'), value: 'int16' },
  { label: t('devices.datatype.uint32'), value: 'uint32' },
  { label: t('devices.datatype.int32'), value: 'int32' },
  { label: t('devices.datatype.float32'), value: 'float32' },
  { label: t('devices.datatype.float32_swap'), value: 'float32_swap' },
  { label: t('devices.datatype.float64'), value: 'float64' },
  { label: t('devices.datatype.uint64'), value: 'uint64' },
  { label: t('devices.datatype.int64'), value: 'int64' },
  { label: t('devices.datatype.bool'), value: 'bool' },
  { label: t('devices.datatype.string'), value: 'string' }
]

const knxDataTypes = [
  { label: t('devices.datatype_knx.switch'), value: 'switch' },
  { label: t('devices.datatype_knx.bool'), value: 'bool' },
  { label: t('devices.datatype_knx.binary'), value: 'binary' },
  { label: t('devices.datatype_knx.percent'), value: 'percent' },
  { label: t('devices.datatype_knx.brightness'), value: 'brightness' },
  { label: t('devices.datatype_knx.dimming'), value: 'dimming' },
  { label: t('devices.datatype_knx.blinds'), value: 'blinds' },
  { label: t('devices.datatype_knx.temperature'), value: 'temperature' },
  { label: t('devices.datatype_knx.humidity'), value: 'humidity' },
  { label: t('devices.datatype_knx.co2'), value: 'co2' },
  { label: t('devices.datatype_knx.voltage'), value: 'voltage' },
  { label: t('devices.datatype_knx.current'), value: 'current' },
  { label: t('devices.datatype_knx.power'), value: 'power' },
  { label: t('devices.datatype_knx.energy'), value: 'energy' },
  { label: t('devices.datatype_knx.color_rgb'), value: 'color_rgb' },
  { label: t('devices.datatype_knx.scene'), value: 'scene' },
  { label: t('devices.datatype_knx.float'), value: 'float' },
  { label: t('devices.datatype_knx.string'), value: 'string' }
]

const bacnetDataTypes = [
  { label: t('devices.datatype_bacnet.analogInput'), value: 'analogInput' },
  { label: t('devices.datatype_bacnet.analogOutput'), value: 'analogOutput' },
  { label: t('devices.datatype_bacnet.analogValue'), value: 'analogValue' },
  { label: t('devices.datatype_bacnet.binaryInput'), value: 'binaryInput' },
  { label: t('devices.datatype_bacnet.binaryOutput'), value: 'binaryOutput' },
  { label: t('devices.datatype_bacnet.binaryValue'), value: 'binaryValue' },
  { label: t('devices.datatype_bacnet.multiStateInput'), value: 'multiStateInput' },
  { label: t('devices.datatype_bacnet.multiStateOutput'), value: 'multiStateOutput' },
  { label: t('devices.datatype_bacnet.multiStateValue'), value: 'multiStateValue' }
]

const registerTypes = [
  { label: t('devices.register_type.holding'), value: 'holding' },
  { label: t('devices.register_type.input'), value: 'input' },
  { label: t('devices.register_type.coil'), value: 'coil' },
  { label: t('devices.register_type.discrete_input'), value: 'discrete_input' }
]

const pointFormRules = {
  name: [{ required: true, message: t('devices.point_name_required'), trigger: 'blur' }],
  data_type: [{ required: true, message: t('devices.data_type_required'), trigger: 'blur' }]
}

const handleAddPoint = () => {
  if (!selectedDeviceAsset.value) return
  isEditingPoint.value = false
  editingPointName.value = ''
  const pluginName = currentDevicePluginName.value
  pointForm.value = {
    name: '',
    description: '',
    data_type: pluginName === 'knx' ? 'switch' : pluginName === 'bacnet' ? 'analogInput' : 'uint16',
    standard_data_type: '',
    unit: '',
    enabled: true,
    configJson: '{}',
    metadataJson: '{}',
    tags: '',
    address: 0,
    register_type: 'holding',
    count: 1,
    scale: null,
    offset: null,
    byte_order: 'big',
    word_order: 'big',
    group_address: '',
    status_address: '',
    control_address: '',
    writable: false,
    object_type: 'analogInput',
    object_instance: 0,
    property: 'presentValue',
    alarm_high: null,
    alarm_low: null,
    min: null,
    max: null
  }
  showPointDialog.value = true
}

const handleEditPoint = (point: any) => {
  isEditingPoint.value = true
  editingPointName.value = point.name
  const config = point.config || {}
  const metadata = point.metadata || {}
  pointForm.value = {
    name: point.name,
    description: point.description || '',
    data_type: point.data_type,
    standard_data_type: point.standard_data_type || '',
    unit: point.unit || '',
    enabled: point.enabled,
    configJson: JSON.stringify(config, null, 2),
    metadataJson: JSON.stringify(metadata, null, 2),
    tags: (point.tags || []).join(', '),
    address: config.address ?? 0,
    register_type: config.register_type || 'holding',
    count: config.count ?? 1,
    scale: config.scale ?? null,
    offset: config.offset ?? null,
    byte_order: config.byte_order || 'big',
    word_order: config.word_order || 'big',
    group_address: config.group_address || '',
    status_address: config.status_address || '',
    control_address: config.control_address || '',
    writable: config.writable ?? false,
    object_type: config.object_type || point.data_type || 'analogInput',
    object_instance: config.object_instance ?? 0,
    property: config.property || 'presentValue',
    alarm_high: metadata.alarm_high ?? null,
    alarm_low: metadata.alarm_low ?? null,
    min: metadata.min ?? null,
    max: metadata.max ?? null
  }
  showPointDialog.value = true
}

const buildPointConfig = (): Record<string, unknown> => {
  const pluginName = currentDevicePluginName.value
  const config: Record<string, unknown> = {}
  
  if (pluginName === 'modbus_tcp' || pluginName === 'modbus_rtu') {
    config.address = pointForm.value.address
    config.register_type = pointForm.value.register_type
    config.count = pointForm.value.count
    config.scale = pointForm.value.scale
    config.offset = pointForm.value.offset
    config.byte_order = pointForm.value.byte_order
    config.word_order = pointForm.value.word_order
  } else if (pluginName === 'knx') {
    config.group_address = pointForm.value.group_address
    config.status_address = pointForm.value.status_address || null
    config.control_address = pointForm.value.control_address || null
    config.writable = pointForm.value.writable
    config.scale = pointForm.value.scale
    config.offset = pointForm.value.offset
  } else if (pluginName === 'bacnet') {
    config.object_type = pointForm.value.object_type
    config.object_instance = pointForm.value.object_instance
    config.property = pointForm.value.property
    config.scale = pointForm.value.scale
    config.offset = pointForm.value.offset
  }
  
  return config
}

const buildPointMetadata = (): Record<string, unknown> => {
  const metadata: Record<string, unknown> = {}
  
  if (pointForm.value.alarm_high !== null) {
    metadata.alarm_high = pointForm.value.alarm_high
  }
  if (pointForm.value.alarm_low !== null) {
    metadata.alarm_low = pointForm.value.alarm_low
  }
  if (pointForm.value.min !== null) {
    metadata.min = pointForm.value.min
  }
  if (pointForm.value.max !== null) {
    metadata.max = pointForm.value.max
  }
  
  return metadata
}

const handleSavePoint = async () => {
  if (!pointFormRef.value) return
  try {
    await pointFormRef.value.validate()
  } catch {
    return
  }

  const config = buildPointConfig()
  const metadata = buildPointMetadata()

  savingPoint.value = true
  try {
    const asset = selectedDeviceAsset.value!
    if (isEditingPoint.value) {
      const updates: Record<string, unknown> = {
        description: pointForm.value.description,
        data_type: pointForm.value.data_type,
        unit: pointForm.value.unit,
        enabled: pointForm.value.enabled,
        config,
        metadata,
        tags: pointForm.value.tags ? pointForm.value.tags.split(',').map(tag => tag.trim()).filter(Boolean) : []
      }
      await pointStore.updatePoint(asset, editingPointName.value, updates)
      ElMessage.success(t('devices.point_updated'))
    } else {
      const point: PointConfig = {
        name: pointForm.value.name,
        description: pointForm.value.description || undefined,
        data_type: pointForm.value.data_type,
        unit: pointForm.value.unit || undefined,
        enabled: pointForm.value.enabled,
        config,
        metadata,
        tags: pointForm.value.tags ? pointForm.value.tags.split(',').map(tag => tag.trim()).filter(Boolean) : []
      }
      await pointStore.addPoint(asset, point)
      ElMessage.success(t('devices.point_added'))
    }
    showPointDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : t('devices.unknown_error'))
    ElMessage.error(isEditingPoint.value ? t('devices.update_point_failed', { detail }) : t('devices.add_point_failed', { detail }))
  } finally {
    savingPoint.value = false
  }
}

const handleDeletePoint = (pointName: string) => {
  if (!selectedDeviceAsset.value) return
  ElMessageBox.confirm(
    t('devices.delete_point_confirm', { name: pointName }),
    t('devices.delete_confirm'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      await pointStore.removePoint(selectedDeviceAsset.value!, pointName)
      ElMessage.success(t('devices.point_deleted'))
    } catch (e: unknown) {
      ElMessage.error(t('devices.delete_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
    }
  }).catch(() => {})
}

const handleWritePoint = (point: any) => {
  if (!selectedDeviceAsset.value) return
  const isDigital = point.type === 'digital' || point.standard_data_type === 'bool'
  writeForm.value = {
    deviceAsset: selectedDeviceAsset.value,
    pointName: point.name,
    pointType: isDigital ? 'digital' : 'analog',
    unit: point.unit || '',
    currentValue: point.currentValue !== undefined && point.currentValue !== null
      ? String(point.currentValue)
      : '--',
    value: '',
    boolValue: point.currentValue === true || point.currentValue === 1
  }
  showWriteDialog.value = true
}

const handleWriteSubmit = async () => {
  writing.value = true
  try {
    let value: number | boolean | string
    if (writeForm.value.pointType === 'digital') {
      value = writeForm.value.boolValue
    } else {
      const numVal = Number(writeForm.value.value)
      if (writeForm.value.value.trim() !== '' && !isNaN(numVal)) {
        value = numVal
      } else {
        value = writeForm.value.value
      }
    }

    const result = await pointStore.writePoint(
      writeForm.value.deviceAsset,
      writeForm.value.pointName,
      value
    )

    if (result.success) {
      ElMessage.success(result.message)
      showWriteDialog.value = false
    } else {
      ElMessage.error(result.message)
    }
  } catch (e: unknown) {
    ElMessage.error(t('devices.write_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
  } finally {
    writing.value = false
  }
}

const handleExportYaml = () => {
  const devices = deviceStore.devices.map(d => {
    const clean: Record<string, unknown> = {
      asset: d.asset,
      name: d.name,
      enabled: d.enabled
    }
    if (d.description) clean.description = d.description
    clean.plugin = d.plugin
    if (d.points && d.points.length > 0) {
      clean.points = d.points.map(p => {
        const pt: Record<string, unknown> = {
          name: p.name,
          data_type: p.data_type,
          enabled: p.enabled,
          config: p.config
        }
        if (p.description) pt.description = p.description
        if (p.unit) pt.unit = p.unit
        if (p.metadata && Object.keys(p.metadata).length > 0) pt.metadata = p.metadata
        if (p.tags && p.tags.length > 0) pt.tags = p.tags
        return pt
      })
    }
    if (d.tags && d.tags.length > 0) clean.tags = d.tags
    if (d.metadata && Object.keys(d.metadata).length > 0) clean.metadata = d.metadata
    return clean
  })

  const content = yaml.dump({ devices }, { 
    indent: 2, 
    lineWidth: 120,
    noRefs: true,
    sortKeys: false
  })
  const blob = new Blob([content], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `xagent-devices-${new Date().toISOString().slice(0, 10)}.yaml`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(t('devices.export_success', { count: devices.length }))
}

const importFileRef = ref<HTMLInputElement | null>(null)

const handleImportYaml = () => {
  importFileRef.value?.click()
}

const handleImportFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''

  try {
    const text = await file.text()
    const parsed = yaml.load(text) as { devices?: DeviceConfig[] }
    if (!parsed.devices || !Array.isArray(parsed.devices)) {
      ElMessage.error(t('devices.invalid_yaml'))
      return
    }

    const devices = parsed.devices as DeviceConfig[]
    await ElMessageBox.confirm(
      t('devices.import_confirm_msg', { count: devices.length }),
      t('devices.import_confirm'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'info' }
    )

    const result = await deviceStore.batchCreate(devices)
    if (result.failed > 0) {
      ElMessage.warning(t('devices.import_partial', { succeeded: result.succeeded, failed: result.failed }))
    } else {
      ElMessage.success(t('devices.import_success', { count: result.succeeded }))
    }
    await pointStore.fetchDevicesWithPoints()
  } catch (e: unknown) {
    if ((e as any) !== 'cancel') {
      ElMessage.error(t('devices.import_failed', { detail: e instanceof Error ? e.message : t('devices.unknown_error') }))
    }
  }
}

onMounted(async () => {
  await deviceStore.fetchDevices()
  await deviceStore.fetchConnectionStatus()
  await pointStore.fetchDevicesWithPoints()
})
</script>

<template>
  <div class="devices-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          :placeholder="$t('devices.search_placeholder')"
          :prefix-icon="Search"
          clearable
          class="toolbar-search"
          @input="handleSearch"
        />
        <el-select 
          v-model="statusFilter" 
          :placeholder="$t('devices.status_filter')" 
          clearable
          class="toolbar-filter"
          @change="handleFilterChange"
        >
          <el-option :label="$t('devices.all')" value="" />
          <el-option :label="$t('devices.online')" value="online" />
          <el-option :label="$t('devices.offline')" value="offline" />
        </el-select>
        <div class="toolbar-stats">
          <span class="stat-item">
            <span class="stat-value">{{ deviceStore.totalDevices }}</span>
            <span class="stat-label">{{ $t('devices.devices_label') }}</span>
          </span>
          <span class="stat-divider">/</span>
          <span class="stat-item stat-online">
            <span class="stat-value">{{ deviceStore.onlineDevices }}</span>
            <span class="stat-label">{{ $t('devices.online_label') }}</span>
          </span>
        </div>
      </div>
      <div class="toolbar-right">
        <el-button v-if="userStore.hasPermission('devices', 'create')" type="primary" :icon="Plus" @click="handleAddDevice">
          {{ $t('devices.add_device') }}
        </el-button>
        <el-button :icon="Download" @click="handleExportYaml">
          {{ $t('common.export') }}
        </el-button>
        <el-button v-if="userStore.hasPermission('devices', 'create')" :icon="Upload" @click="handleImportYaml">
          {{ $t('common.import') }}
        </el-button>
        <el-button :icon="Refresh" @click="handleRefresh" :loading="deviceStore.loading">
          {{ $t('common.refresh') }}
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="deviceStore.error"
      :title="deviceStore.error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 16px"
    />
    
    <div v-if="isCompactMode" class="main-content compact-mode">
      <div class="compact-tabs">
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'devices' }"
          @click="activeTab = 'devices'"
        >
          {{ $t('devices.device_list') }}
          <span v-if="selectedDeviceAsset" class="tab-badge">{{ deviceStore.getDeviceByAsset(selectedDeviceAsset)?.name }}</span>
        </div>
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'points', disabled: !selectedDeviceAsset }"
          @click="selectedDeviceAsset && (activeTab = 'points')"
        >
          {{ $t('devices.point_list') }}
          <span v-if="selectedDeviceAsset" class="tab-count">{{ getDevicePoints(selectedDeviceAsset).length }}</span>
        </div>
      </div>
      
      <div v-show="activeTab === 'devices'" class="compact-panel device-panel">
        <div v-if="deviceStore.loading && deviceStore.southDevices.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>{{ $t('devices.loading_devices') }}</p>
        </div>

        <div v-else-if="filteredSouthDevices.length === 0" class="empty-state">
          <p>{{ $t('devices.no_devices') }}</p>
        </div>

        <div v-else class="device-grid">
          <div 
            v-for="device in filteredSouthDevices" 
            :key="device.asset" 
            class="device-card-compact"
            :class="{ 
              offline: device.connectionStatus !== 'online',
              selected: selectedDeviceAsset === device.asset 
            }"
            @click="handleViewPoints(device.asset); activeTab = 'points'"
          >
            <div class="device-card-header">
              <div class="device-card-status" :class="{ online: device.connectionStatus === 'online' }">
                <el-icon v-if="device.connectionStatus === 'online'"><CircleCheck /></el-icon>
                <el-icon v-else><CircleClose /></el-icon>
              </div>
              <div class="device-card-info">
                <div class="device-card-name">{{ device.name }}</div>
                <div class="device-card-meta">
                  <span>{{ device.pluginName }}</span>
                  <span>{{ device.pointCount }} {{ $t('devices.points_suffix') }}</span>
                </div>
              </div>
            </div>
            <div class="device-card-actions">
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="device.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleDevice(device.asset)"
                @click.stop
              />
              <div class="action-buttons" @click.stop>
                <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" link :size="isTouch ? 'default' : 'small'" @click="handleEditDevice(device)">
                  {{ $t('common.edit') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'delete')" type="danger" link :size="isTouch ? 'default' : 'small'" @click="handleDeleteDevice(device)">
                  {{ $t('common.delete') }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-show="activeTab === 'points'" class="compact-panel points-panel">
        <div v-if="!selectedDeviceAsset" class="empty-points">
          <el-icon :size="48"><TrendCharts /></el-icon>
          <p>{{ $t('devices.select_device_first') }}</p>
          <el-button type="primary" @click="activeTab = 'devices'">{{ $t('devices.back_to_device_list') }}</el-button>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <div class="panel-header-left">
              <el-button link @click="activeTab = 'devices'">
                <el-icon><RefreshRight /></el-icon>
                {{ $t('devices.back_to_device') }}
              </el-button>
            </div>
            <span class="panel-title">{{ deviceStore.getDeviceByAsset(selectedDeviceAsset)?.name || selectedDeviceAsset }}</span>
            <el-button v-if="userStore.hasPermission('devices', 'create')" type="primary" :icon="Plus" size="small" @click="handleAddPoint">
              {{ $t('devices.add_point') }}
            </el-button>
          </div>
          
          <el-table 
            :data="getDevicePoints(selectedDeviceAsset)" 
            stripe 
            style="width: 100%; flex: 1;"
            height="100%"
          >
            <el-table-column prop="name" :label="$t('devices.point_name')" min-width="120" />
            <el-table-column :label="$t('devices.current_value')" min-width="100">
              <template #default="{ row }">
                <span v-if="row.currentValue !== undefined && row.currentValue !== null" class="current-value">
                  {{ row.currentValue }}{{ row.unit ? ' ' + row.unit : '' }}
                </span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.data_type')" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.data_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.quality')" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.quality" size="small" :type="row.quality === 'good' ? 'success' : row.quality === 'bad' ? 'danger' : 'warning'">
                  {{ row.quality === 'good' ? $t('devices.quality_good') : row.quality === 'bad' ? $t('devices.quality_bad') : $t('devices.quality_uncertain') }}
                </el-tag>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.operation')" width="220" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewTrend(selectedDeviceAsset!, row.name)">
                  {{ $t('devices.trend') }}
                </el-button>
                <el-button v-if="row.writable && userStore.hasPermission('devices', 'update')" type="warning" link size="small" @click="handleWritePoint(row)">
                  {{ $t('devices.write') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" link size="small" @click="handleEditPoint(row)">
                  {{ $t('common.edit') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'delete')" type="danger" link size="small" @click="handleDeletePoint(row.name)">
                  {{ $t('common.delete') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </div>
    
    <div v-else class="main-content">
      <div class="device-list-panel">
        <div class="panel-header">
          <span class="panel-title">{{ $t('devices.device_list') }}</span>
          <span class="device-count">{{ filteredSouthDevices.length }} {{ $t('devices.devices_count') }}</span>
        </div>
        
        <div v-if="deviceStore.loading && deviceStore.southDevices.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>{{ $t('devices.loading_devices') }}</p>
        </div>

        <div v-else-if="filteredSouthDevices.length === 0" class="empty-state">
          <p>{{ $t('devices.no_devices') }}</p>
        </div>

        <div v-else class="device-list">
          <div 
            v-for="device in filteredSouthDevices" 
            :key="device.asset" 
            class="device-item"
            :class="{ 
              offline: device.connectionStatus !== 'online',
              selected: selectedDeviceAsset === device.asset 
            }"
            @click="handleViewPoints(device.asset)"
          >
            <div class="device-item-status" :class="{ online: device.connectionStatus === 'online' }">
              <el-icon v-if="device.connectionStatus === 'online'"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
            <div class="device-item-content">
              <div class="device-item-header">
                <span class="device-item-name">{{ device.name }}</span>
              </div>
              <div class="device-item-meta">
                <span>{{ device.pluginName }}</span>
                <span>{{ device.pointCount }} {{ $t('devices.points_suffix') }}</span>
              </div>
            </div>
            <div class="device-item-actions" @click.stop>
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="device.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleDevice(device.asset)"
              />
              <el-dropdown trigger="click" @command="(cmd: string) => {
                if (cmd === 'edit') handleEditDevice(device)
                else if (cmd === 'delete') handleDeleteDevice(device)
                else if (cmd === 'reload') handleReloadDevice(device.asset)
              }">
                <el-button type="info" link :size="isTouch ? 'default' : 'small'" class="more-btn">
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="edit" :icon="Edit">{{ $t('common.edit') }}</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="reload" :icon="RefreshRight">{{ $t('devices.hot_reload') }}</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'delete')" command="delete" :icon="Delete" divided>
                      <span style="color: #f56c6c">{{ $t('common.delete') }}</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </div>
      
      <div class="points-panel">
        <div v-if="!selectedDeviceAsset" class="empty-points">
          <el-icon :size="48"><TrendCharts /></el-icon>
          <p>{{ $t('devices.select_device_to_view') }}</p>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <span class="panel-title">{{ deviceStore.getDeviceByAsset(selectedDeviceAsset)?.name || selectedDeviceAsset }} {{ $t('devices.point_list') }}</span>
            <div class="points-actions">
              <el-button v-if="userStore.hasPermission('devices', 'create')" type="primary" :icon="Plus" size="small" @click="handleAddPoint">
                {{ $t('devices.add_point') }}
              </el-button>
            </div>
          </div>
          
          <el-table 
            :data="getDevicePoints(selectedDeviceAsset)" 
            stripe 
            style="width: 100%; flex: 1;"
            height="100%"
          >
            <el-table-column prop="name" :label="$t('devices.point_name')" width="150" />
            <el-table-column prop="description" :label="$t('devices.description')" width="150" />
            <el-table-column :label="$t('devices.current_value')" width="120">
              <template #default="{ row }">
                <span v-if="row.currentValue !== undefined && row.currentValue !== null" class="current-value">
                  {{ row.currentValue }}{{ row.unit ? ' ' + row.unit : '' }}
                </span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.data_type')" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.data_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.quality')" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.quality" size="small" :type="row.quality === 'good' ? 'success' : row.quality === 'bad' ? 'danger' : 'warning'">
                  {{ row.quality === 'good' ? $t('devices.quality_good') : row.quality === 'bad' ? $t('devices.quality_bad') : $t('devices.quality_uncertain') }}
                </el-tag>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.update_time')" width="170">
              <template #default="{ row }">
                <span v-if="row.lastUpdate">{{ row.lastUpdate }}</span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.config')" min-width="150">
              <template #default="{ row }">
                <span class="config-preview">{{ JSON.stringify(row.config) }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="$t('devices.operation')" width="220" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewTrend(selectedDeviceAsset!, row.name)">
                  {{ $t('devices.trend') }}
                </el-button>
                <el-button v-if="row.writable && userStore.hasPermission('devices', 'update')" type="warning" link size="small" @click="handleWritePoint(row)">
                  {{ $t('devices.write') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" link size="small" @click="handleEditPoint(row)">
                  {{ $t('common.edit') }}
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'delete')" type="danger" link size="small" @click="handleDeletePoint(row.name)">
                  {{ $t('common.delete') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </div>
    
    <el-dialog 
      v-model="showDeviceDialog" 
      :title="isEditing ? $t('devices.edit_device') : $t('devices.add_device')"
      width="min(600px, 90vw)"
      :close-on-click-modal="false"
    >
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceFormRules" label-width="100px">
        <el-form-item :label="$t('devices.asset_label')" prop="asset">
          <el-input 
            v-model="deviceForm.asset" 
            :placeholder="$t('devices.asset_placeholder')"
            :disabled="isEditing"
          />
        </el-form-item>
        <el-form-item :label="$t('devices.device_name')">
          <el-input v-model="deviceForm.name" :placeholder="$t('devices.device_name_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('devices.description')">
          <el-input v-model="deviceForm.description" type="textarea" :rows="2" :placeholder="$t('devices.device_desc_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('devices.protocol_type')" prop="pluginName">
          <el-select v-model="deviceForm.pluginName" :placeholder="$t('devices.protocol_placeholder')" @change="handlePluginChange">
            <el-option 
              v-for="opt in pluginOptions" 
              :key="opt.value" 
              :label="opt.label" 
              :value="opt.value" 
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('devices.host_label')" prop="host">
          <el-input v-model="deviceForm.host" :placeholder="$t('devices.host_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('devices.port_label')">
          <el-input-number v-model="deviceForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'modbus_tcp' || deviceForm.pluginName === 'modbus_rtu'" :label="$t('devices.slave_id')">
          <el-input-number v-model="deviceForm.slave_id" :min="0" :max="255" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'modbus_tcp' || deviceForm.pluginName === 'modbus_rtu'" :label="$t('devices.interval_label')">
          <el-input-number v-model="deviceForm.interval" :min="1" :max="3600" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.interval_hint_modbus') }}
          </div>
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'bacnet'" :label="$t('devices.device_id')">
          <el-input-number v-model="deviceForm.device_id" :min="0" :max="4194303" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'bacnet'" :label="$t('devices.interval_label')">
          <el-input-number v-model="deviceForm.interval" :min="1" :max="3600" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.interval_hint_bacnet') }}
          </div>
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" :label="$t('devices.local_ip')">
          <el-input v-model="deviceForm.local_ip" :placeholder="$t('devices.local_ip_placeholder')" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" :label="$t('devices.connection_type')">
          <el-select v-model="deviceForm.connection_type" :placeholder="$t('devices.connection_type_placeholder')">
            <el-option :label="$t('devices.connection_automatic')" value="automatic" />
            <el-option :label="$t('devices.connection_tunneling')" value="tunneling" />
            <el-option :label="$t('devices.connection_tunneling_tcp')" value="tunneling_tcp" />
            <el-option :label="$t('devices.connection_routing')" value="routing" />
            <el-option :label="$t('devices.connection_tunneling_tcp_secure')" value="tunneling_tcp_secure" />
            <el-option :label="$t('devices.connection_routing_secure')" value="routing_secure" />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.connection_type_hint') }}
          </div>
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" :label="$t('devices.interval_label')">
          <el-input-number v-model="deviceForm.interval" :min="1" :max="3600" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.interval_hint_knx') }}
          </div>
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" :label="$t('devices.sync_mode')">
          <el-select v-model="deviceForm.sync_mode" :placeholder="$t('devices.sync_mode_placeholder')">
            <el-option :label="$t('devices.sync_smart')" value="smart" />
            <el-option :label="$t('devices.sync_always')" value="always" />
            <el-option :label="$t('devices.sync_passive')" value="passive" />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.sync_mode_hint') }}
          </div>
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" :label="$t('devices.sync_interval')">
          <el-input-number v-model="deviceForm.sync_interval" :min="5" :max="1440" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.sync_interval_hint') }}
          </div>
        </el-form-item>
        <el-form-item :label="$t('devices.timeout_label')">
          <el-input-number v-model="deviceForm.timeout" :min="1" :max="60" />
        </el-form-item>
        <el-form-item :label="$t('devices.enabled_label')">
          <el-switch v-model="deviceForm.enabled" />
        </el-form-item>
        <el-form-item :label="$t('devices.tags_label')">
          <el-input v-model="deviceForm.tags" :placeholder="$t('devices.tags_placeholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeviceDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveDevice" :loading="saving">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog 
      v-model="showPointDialog" 
      :title="isEditingPoint ? $t('devices.edit_point') : $t('devices.add_point')"
      width="min(700px, 92vw)"
      :close-on-click-modal="false"
    >
      <el-form ref="pointFormRef" :model="pointForm" :rules="pointFormRules" label-width="100px">
        <el-form-item :label="$t('devices.point_name')" prop="name">
          <el-input 
            v-model="pointForm.name" 
            :placeholder="$t('devices.point_name_placeholder')"
            :disabled="isEditingPoint"
          />
        </el-form-item>
        <el-form-item :label="$t('devices.description')">
          <el-input v-model="pointForm.description" :placeholder="$t('devices.point_desc_placeholder')" />
        </el-form-item>
        
        <el-divider content-position="left">{{ $t('devices.protocol_config') }}</el-divider>
        
        <template v-if="currentDevicePluginName === 'modbus_tcp' || currentDevicePluginName === 'modbus_rtu'">
          <el-form-item :label="$t('devices.data_type')" prop="data_type">
            <el-select v-model="pointForm.data_type" :placeholder="$t('devices.data_type_placeholder')">
              <el-option 
                v-for="opt in modbusDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('devices.register_address')" prop="address">
            <el-input-number v-model="pointForm.address" :min="0" :max="65535" :placeholder="$t('devices.register_address_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.register_type_label')">
            <el-select v-model="pointForm.register_type" :placeholder="$t('devices.register_type_placeholder')">
              <el-option 
                v-for="opt in registerTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('devices.register_count')">
            <el-input-number v-model="pointForm.count" :min="1" :max="16" :placeholder="$t('devices.register_count_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.scale_factor')">
            <el-input-number v-model="pointForm.scale" :placeholder="$t('devices.scale_placeholder')" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item :label="$t('devices.offset')">
            <el-input-number v-model="pointForm.offset" :placeholder="$t('devices.offset_placeholder')" :precision="4" clearable />
          </el-form-item>
          <el-form-item :label="$t('devices.byte_order')">
            <el-radio-group v-model="pointForm.byte_order">
              <el-radio value="big">{{ $t('devices.big_endian') }}</el-radio>
              <el-radio value="little">{{ $t('devices.little_endian') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="$t('devices.word_order')">
            <el-radio-group v-model="pointForm.word_order">
              <el-radio value="big">{{ $t('devices.big_endian') }}</el-radio>
              <el-radio value="little">{{ $t('devices.little_endian_siemens') }}</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>
        
        <template v-else-if="currentDevicePluginName === 'knx'">
          <el-form-item :label="$t('devices.data_type')" prop="data_type">
            <el-select v-model="pointForm.data_type" :placeholder="$t('devices.data_type_placeholder')">
              <el-option 
                v-for="opt in knxDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('devices.group_address')" prop="group_address">
            <el-input v-model="pointForm.group_address" :placeholder="$t('devices.group_address_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.status_address')">
            <el-input v-model="pointForm.status_address" :placeholder="$t('devices.status_address_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.control_address')">
            <el-input v-model="pointForm.control_address" :placeholder="$t('devices.control_address_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.writable')">
            <el-switch v-model="pointForm.writable" />
          </el-form-item>
          <el-form-item :label="$t('devices.scale_factor')">
            <el-input-number v-model="pointForm.scale" :placeholder="$t('devices.scale_optional')" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item :label="$t('devices.offset')">
            <el-input-number v-model="pointForm.offset" :placeholder="$t('devices.offset_optional')" :precision="4" clearable />
          </el-form-item>
        </template>
        
        <template v-else-if="currentDevicePluginName === 'bacnet'">
          <el-form-item :label="$t('devices.object_type')" prop="object_type">
            <el-select v-model="pointForm.object_type" :placeholder="$t('devices.object_type_placeholder')" @change="pointForm.data_type = pointForm.object_type">
              <el-option 
                v-for="opt in bacnetDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('devices.object_instance')" prop="object_instance">
            <el-input-number v-model="pointForm.object_instance" :min="0" :placeholder="$t('devices.object_instance_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.property_label')">
            <el-input v-model="pointForm.property" :placeholder="$t('devices.property_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.scale_factor')">
            <el-input-number v-model="pointForm.scale" :placeholder="$t('devices.scale_optional')" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item :label="$t('devices.offset')">
            <el-input-number v-model="pointForm.offset" :placeholder="$t('devices.offset_optional')" :precision="4" clearable />
          </el-form-item>
        </template>
        
        <template v-else>
          <el-form-item :label="$t('devices.data_type')" prop="data_type">
            <el-input v-model="pointForm.data_type" :placeholder="$t('devices.protocol_type_placeholder')" />
          </el-form-item>
          <el-form-item :label="$t('devices.protocol_config_label')">
            <el-input 
              v-model="pointForm.configJson" 
              type="textarea" 
              :rows="4" 
              :placeholder="$t('devices.protocol_config_placeholder')"
            />
          </el-form-item>
        </template>
        
        <el-divider content-position="left">{{ $t('devices.common_config') }}</el-divider>
        
        <el-form-item :label="$t('devices.standard_type')">
          <el-input 
            :value="pointForm.standard_data_type || $t('devices.auto_derived')" 
            disabled 
            :placeholder="$t('devices.auto_derived_placeholder')"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ $t('devices.standard_type_hint') }}
          </div>
        </el-form-item>
        <el-form-item :label="$t('devices.unit_label')">
          <el-input v-model="pointForm.unit" :placeholder="$t('devices.unit_placeholder')" />
        </el-form-item>
        
        <el-divider content-position="left">{{ $t('devices.metadata_label') }}</el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="$t('devices.min_value')">
              <el-input-number v-model="pointForm.min" :placeholder="$t('devices.optional')" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('devices.max_value')">
              <el-input-number v-model="pointForm.max" :placeholder="$t('devices.optional')" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="$t('devices.high_alarm')">
              <el-input-number v-model="pointForm.alarm_high" :placeholder="$t('devices.optional')" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('devices.low_alarm')">
              <el-input-number v-model="pointForm.alarm_low" :placeholder="$t('devices.optional')" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item :label="$t('devices.enabled_label')">
          <el-switch v-model="pointForm.enabled" />
        </el-form-item>
        <el-form-item :label="$t('devices.tags_label')">
          <el-input v-model="pointForm.tags" :placeholder="$t('devices.tags_point_placeholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPointDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSavePoint" :loading="savingPoint">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
    
    <el-dialog 
      v-model="showWriteDialog" 
      :title="$t('devices.write_point_title')"
      width="min(480px, 90vw)"
      :close-on-click-modal="false"
    >
      <div class="write-info">
        <div class="write-info-row">
          <span class="write-info-label">{{ $t('devices.device_label') }}</span>
          <span class="write-info-value">{{ deviceStore.getDeviceByAsset(writeForm.deviceAsset)?.name || writeForm.deviceAsset }}</span>
        </div>
        <div class="write-info-row">
          <span class="write-info-label">{{ $t('devices.point_label') }}</span>
          <span class="write-info-value">{{ writeForm.pointName }}</span>
        </div>
        <div class="write-info-row">
          <span class="write-info-label">{{ $t('devices.current_value_label') }}</span>
          <span class="write-info-value current-value">{{ writeForm.currentValue }}{{ writeForm.unit ? ' ' + writeForm.unit : '' }}</span>
        </div>
      </div>
      <el-divider />
      <div class="write-form">
        <template v-if="writeForm.pointType === 'digital'">
          <div class="write-bool-control">
            <span class="write-bool-label">{{ $t('devices.target_value') }}</span>
            <el-switch 
              v-model="writeForm.boolValue"
              :active-text="$t('devices.on')"
              :inactive-text="$t('devices.off')"
              style="--el-switch-on-color: #27ae60"
            />
          </div>
        </template>
        <template v-else>
          <el-input 
            v-model="writeForm.value" 
            :placeholder="writeForm.currentValue !== '--' ? $t('devices.current_value_hint', { value: writeForm.currentValue }) : $t('devices.enter_value')"
            clearable
          >
            <template v-if="writeForm.unit" #append>{{ writeForm.unit }}</template>
          </el-input>
          <div v-if="writeForm.unit" class="write-hint">
            {{ $t('devices.write_hint') }}
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="showWriteDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button 
          type="warning" 
          :loading="writing" 
          :disabled="writeForm.pointType !== 'digital' && !writeForm.value.trim()"
          @click="handleWriteSubmit"
        >
          {{ $t('devices.confirm_write') }}
        </el-button>
      </template>
    </el-dialog>
    
    <el-drawer
      v-model="showTrend"
      :title="$t('devices.point_trend')"
      direction="rtl"
      size="70%"
      :with-header="false"
    >
      <PointTrend 
        :device-name="selectedPointForTrend?.deviceAsset"
        :point-name="selectedPointForTrend?.pointName"
        @close="handleCloseTrend"
      />
    </el-drawer>

    <input
      ref="importFileRef"
      type="file"
      accept=".yaml,.yml"
      style="display: none"
      @change="handleImportFileChange"
    />
  </div>
</template>

<style scoped>
.devices-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-search {
  width: 250px;
}

.toolbar-filter {
  width: 120px;
}

.toolbar-stats {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-left: 8px;
  padding-left: 12px;
  border-left: 1px solid #ebeef5;
}

.stat-item {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-divider {
  color: #dcdfe6;
  font-size: 14px;
  margin: 0 2px;
}

.stat-online .stat-value {
  color: #27ae60;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.main-content {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.main-content.compact-mode {
  flex-direction: column;
}

.compact-tabs {
  display: flex;
  background: #fff;
  border-radius: 8px;
  padding: 4px;
  gap: 4px;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.compact-tab {
  flex: 1;
  padding: 12px 16px;
  text-align: center;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  background: transparent;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.compact-tab:hover {
  background: #f5f7fa;
}

.compact-tab.active {
  background: #409eff;
  color: #fff;
}

.compact-tab.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tab-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-tab:not(.active) .tab-badge {
  background: #e6f7ff;
  color: #409eff;
}

.tab-count {
  font-size: 12px;
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
}

.compact-tab:not(.active) .tab-count {
  background: #f0f0f0;
  color: #606266;
}

.compact-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.device-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  align-content: start;
}

.device-card-compact {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.device-card-compact:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.device-card-compact.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.device-card-compact.offline {
  opacity: 0.7;
}

.device-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.device-card-status {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #ffebee;
  color: #e74c3c;
}

.device-card-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.device-card-info {
  flex: 1;
  min-width: 0;
}

.device-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.device-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.action-buttons {
  display: flex;
  gap: 4px;
}

.panel-header-left {
  display: flex;
  align-items: center;
}

.device-list-panel {
  width: 320px;
  min-width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.device-count {
  font-size: 13px;
  color: #909399;
}

.device-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.device-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 8px;
  border: 1px solid transparent;
}

.device-item:hover {
  background: #f5f7fa;
}

.device-item.selected {
  background: #ecf5ff;
  border-color: #409eff;
}

.device-item.offline {
  opacity: 0.7;
}

.device-item-status {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #ffebee;
  color: #e74c3c;
}

.device-item-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.device-item-content {
  flex: 1;
  min-width: 0;
}

.device-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.device-item-name {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.device-item-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.more-btn {
  padding: 4px;
  border-radius: 4px;
}

.more-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.points-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.empty-points {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
}

.empty-points p {
  margin-top: 16px;
  font-size: 14px;
}

.points-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-preview {
  font-size: 12px;
  color: #7f8c8d;
  word-break: break-all;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}

.text-muted {
  color: #c0c4cc;
}

.current-value {
  font-weight: 600;
  color: #409eff;
}

.write-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.write-info-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.write-info-label {
  width: 60px;
  flex-shrink: 0;
  font-size: 13px;
  color: #909399;
}

.write-info-value {
  font-size: 14px;
  color: #2c3e50;
}

.write-info-value.current-value {
  color: #409eff;
  font-weight: 600;
}

.write-form {
  padding: 0 4px;
}

.write-bool-control {
  display: flex;
  align-items: center;
  gap: 16px;
}

.write-bool-label {
  font-size: 14px;
  color: #606266;
}

.write-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  line-height: 1.5;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #95a5a6;
}

.loading-state p {
  margin-top: 12px;
  font-size: 14px;
}

.empty-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
  color: #95a5a6;
  font-size: 14px;
}

@media (max-width: 1200px) {
  .toolbar-search {
    width: 200px;
  }

  .device-list-panel {
    width: 280px;
    min-width: 240px;
  }
}

@media (max-width: 1024px) {
  .toolbar-search {
    width: 180px;
  }

  .toolbar-filter {
    width: 110px;
  }
}

@media (max-width: 900px) {
  .main-content {
    flex-direction: column;
  }

  .device-list-panel {
    width: 100%;
    min-width: 0;
    max-height: 280px;
  }

  .points-panel {
    min-height: 300px;
    flex: 1;
  }

  .toolbar-search {
    width: 100%;
    order: 1;
  }

  .toolbar-filter {
    width: 140px;
    order: 2;
  }

  .toolbar-stats {
    order: 3;
    margin-left: 0;
    padding-left: 0;
    border-left: none;
  }

  .toolbar-right {
    order: 4;
    margin-left: auto;
  }
}

@media (max-width: 600px) {
  .toolbar {
    padding: 10px 12px;
  }

  .toolbar-search {
    width: 100%;
  }

  .toolbar-filter {
    width: 100%;
  }

  .toolbar-stats {
    width: 100%;
    justify-content: center;
  }

  .device-list-panel {
    max-height: 220px;
  }

  .device-item {
    padding: 10px;
  }

  .device-item-meta {
    flex-direction: column;
    gap: 2px;
  }
}

@media (pointer: coarse) {
  .device-item {
    padding: 14px 12px;
    min-height: 56px;
  }

  .device-item-actions {
    gap: 8px;
  }

  .more-btn {
    padding: 8px;
    min-width: 36px;
    min-height: 36px;
  }

  .device-item-status {
    width: 36px;
    height: 36px;
  }

  .el-button {
    min-height: 36px;
  }

  .el-table .el-button:not(.is-link) {
    min-height: 32px;
    padding: 6px 12px;
  }

  .el-table .el-button.is-link {
    padding: 4px 8px;
  }
}

@media (max-width: 1024px) {
  .device-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 8px;
    padding: 8px;
  }

  .device-card-compact {
    padding: 12px;
  }

  .compact-tab {
    padding: 8px 12px;
    font-size: 13px;
  }

  .panel-header {
    padding: 8px 12px;
  }

  .toolbar {
    padding: 10px 12px;
    gap: 8px;
  }

  .toolbar-right {
    flex-wrap: wrap;
  }
}

@media (max-height: 700px) {
  .toolbar {
    padding: 8px 12px;
    gap: 8px;
  }

  .compact-tabs {
    padding: 2px;
    gap: 2px;
  }

  .compact-tab {
    padding: 6px 10px;
    font-size: 13px;
  }

  .device-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px;
    padding: 6px;
  }

  .device-card-compact {
    padding: 10px;
  }

  .device-card-header {
    margin-bottom: 6px;
  }

  .panel-header {
    padding: 6px 10px;
    min-height: 36px;
  }

  .panel-title {
    font-size: 14px;
  }

  .loading-state {
    padding: 30px 0;
  }

  .empty-state {
    padding: 30px 0;
  }
}
</style>
