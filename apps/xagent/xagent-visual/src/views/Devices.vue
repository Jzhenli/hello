<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDeviceStore } from '@/stores/devices'
import { usePointStore } from '@/stores/points'
import type { DeviceConfig, PointConfig, StandardDataType } from '@/api/types'
import type { DeviceListItem } from '@/stores/devices'
import { 
  Plus, 
  Upload, 
  Download, 
  Refresh,
  CircleCheck,
  CircleClose,
  Search,
  TrendCharts,
  Delete
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PointTrend from '@/components/PointTrend.vue'

const deviceStore = useDeviceStore()
const pointStore = usePointStore()

const searchQuery = ref('')
const statusFilter = ref('')
const selectedDeviceAsset = ref<string | null>(null)
const showTrend = ref(false)
const selectedPointForTrend = ref<{ deviceAsset: string; pointName: string } | null>(null)

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
    ElMessage.success('设备状态已切换')
  } catch (e: unknown) {
    ElMessage.error('操作失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

const handleRefresh = async () => {
  await deviceStore.fetchDevices()
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
  device_id: 1234,
  tags: ''
})
const deviceFormRef = ref()
const isEditing = ref(false)
const editingAsset = ref('')
const saving = ref(false)

const pluginOptions = [
  { 
    label: 'Modbus TCP', 
    value: 'modbus_tcp', 
    defaultPort: 502,
    defaultConfig: { slave_id: 1, timeout: 5 }
  },
  { 
    label: 'Modbus RTU', 
    value: 'modbus_rtu', 
    defaultPort: 0,
    defaultConfig: { slave_id: 1, timeout: 5 }
  },
  { 
    label: 'KNX', 
    value: 'knx', 
    defaultPort: 3671,
    defaultConfig: { local_ip: '', timeout: 5 }
  },
  { 
    label: 'BACnet', 
    value: 'bacnet', 
    defaultPort: 47808,
    defaultConfig: { device_id: 1234, timeout: 5 }
  }
]

const deviceFormRules = {
  asset: [{ required: true, message: '请输入资产标识', trigger: 'blur' }],
  pluginName: [{ required: true, message: '请选择协议类型', trigger: 'change' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }]
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
      const baseConfig: Record<string, unknown> = {
        host: deviceForm.value.host,
        port: deviceForm.value.port
      }
      
      if (deviceForm.value.pluginName === 'modbus_tcp' || deviceForm.value.pluginName === 'modbus_rtu') {
        baseConfig.slave_id = deviceForm.value.slave_id
        baseConfig.timeout = deviceForm.value.timeout
      } else if (deviceForm.value.pluginName === 'knx') {
        baseConfig.gateway_ip = deviceForm.value.gateway_ip || deviceForm.value.host
        baseConfig.gateway_port = deviceForm.value.port
        if (deviceForm.value.local_ip) {
          baseConfig.local_ip = deviceForm.value.local_ip
        }
        baseConfig.timeout = deviceForm.value.timeout
      } else if (deviceForm.value.pluginName === 'bacnet') {
        baseConfig.device_id = deviceForm.value.device_id
        baseConfig.timeout = deviceForm.value.timeout
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
        tags: deviceForm.value.tags ? deviceForm.value.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      })
      ElMessage.success('设备已更新')
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
        tags: deviceForm.value.tags ? deviceForm.value.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      }
      await deviceStore.createDevice(device)
      ElMessage.success('设备已创建')
    }
    showDeviceDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : '未知错误')
    ElMessage.error(isEditing.value ? '更新失败: ' + detail : '创建失败: ' + detail)
  } finally {
    saving.value = false
  }
}

const handleDeleteDevice = (device: DeviceListItem) => {
  ElMessageBox.confirm(
    `确定要删除设备 "${device.name}" (${device.asset}) 吗？此操作不可恢复。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deviceStore.deleteDevice(device.asset)
      if (selectedDeviceAsset.value === device.asset) {
        selectedDeviceAsset.value = null
      }
      ElMessage.success('设备已删除')
    } catch (e: unknown) {
      ElMessage.error('删除失败: ' + (e instanceof Error ? e.message : '未知错误'))
    }
  }).catch(() => {})
}

const handleReloadDevice = async (asset: string) => {
  try {
    await deviceStore.reloadDevice(asset)
    ElMessage.success('设备已热重载')
  } catch (e: unknown) {
    ElMessage.error('热重载失败: ' + (e instanceof Error ? e.message : '未知错误'))
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

const getStatusLabel = (status: string, enabled: boolean) => {
  if (!enabled) return '已停用'
  if (status === 'active') return '在线'
  if (status === 'error') return '错误'
  if (status === 'maintenance') return '维护中'
  return '离线'
}

const getStatusType = (status: string, enabled: boolean) => {
  if (!enabled) return 'info'
  if (status === 'active') return 'success'
  if (status === 'error') return 'danger'
  if (status === 'maintenance') return 'warning'
  return 'info'
}

const getDataTypeLabel = (type?: string) => {
  if (type === 'bool') return '布尔'
  if (type === 'int') return '整数'
  if (type === 'float') return '浮点'
  if (type === 'string') return '字符串'
  return type || '-'
}

const showPointDialog = ref(false)
const pointForm = ref({
  name: '',
  description: '',
  data_type: 'uint16',
  standard_data_type: 'float' as StandardDataType | '',
  unit: '',
  enabled: true,
  configJson: '{}',
  metadataJson: '{}',
  tags: '',
  address: 0,
  register_type: 'holding' as 'holding' | 'input' | 'coil' | 'discrete_input',
  count: 1,
  slave_id: null as number | null,
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

const currentDevicePluginName = computed(() => {
  if (!selectedDeviceAsset.value) return ''
  const device = deviceStore.getDeviceByAsset(selectedDeviceAsset.value)
  return device?.plugin?.name || ''
})

const modbusDataTypes = [
  { label: 'uint16 - 无符号16位整数', value: 'uint16' },
  { label: 'int16 - 有符号16位整数', value: 'int16' },
  { label: 'uint32 - 无符号32位整数', value: 'uint32' },
  { label: 'int32 - 有符号32位整数', value: 'int32' },
  { label: 'float32 - 32位浮点数', value: 'float32' },
  { label: 'float32_swap - 字序交换浮点数', value: 'float32_swap' },
  { label: 'float64 - 64位浮点数', value: 'float64' },
  { label: 'uint64 - 无符号64位整数', value: 'uint64' },
  { label: 'int64 - 有符号64位整数', value: 'int64' },
  { label: 'bool - 布尔值', value: 'bool' },
  { label: 'string - 字符串', value: 'string' }
]

const knxDataTypes = [
  { label: 'switch - 开关', value: 'switch' },
  { label: 'bool - 布尔值', value: 'bool' },
  { label: 'percent - 百分比', value: 'percent' },
  { label: 'temperature - 温度', value: 'temperature' },
  { label: 'brightness - 亮度', value: 'brightness' },
  { label: 'humidity - 湿度', value: 'humidity' },
  { label: 'co2 - CO2浓度', value: 'co2' },
  { label: 'string - 字符串', value: 'string' }
]

const bacnetDataTypes = [
  { label: 'analogInput - 模拟输入', value: 'analogInput' },
  { label: 'analogOutput - 模拟输出', value: 'analogOutput' },
  { label: 'analogValue - 模拟值', value: 'analogValue' },
  { label: 'binaryInput - 二进制输入', value: 'binaryInput' },
  { label: 'binaryOutput - 二进制输出', value: 'binaryOutput' },
  { label: 'binaryValue - 二进制值', value: 'binaryValue' },
  { label: 'multiStateInput - 多状态输入', value: 'multiStateInput' },
  { label: 'multiStateOutput - 多状态输出', value: 'multiStateOutput' },
  { label: 'multiStateValue - 多状态值', value: 'multiStateValue' }
]

const registerTypes = [
  { label: '保持寄存器 (Holding)', value: 'holding' },
  { label: '输入寄存器 (Input)', value: 'input' },
  { label: '线圈 (Coil)', value: 'coil' },
  { label: '离散输入 (Discrete Input)', value: 'discrete_input' }
]

const pointFormRules = {
  name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  data_type: [{ required: true, message: '请输入数据类型', trigger: 'blur' }]
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
    standard_data_type: 'float',
    unit: '',
    enabled: true,
    configJson: '{}',
    metadataJson: '{}',
    tags: '',
    address: 0,
    register_type: 'holding',
    count: 1,
    slave_id: null,
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
    slave_id: config.slave_id ?? null,
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
    if (pointForm.value.count && pointForm.value.count > 1) {
      config.count = pointForm.value.count
    }
    if (pointForm.value.slave_id !== null) {
      config.slave_id = pointForm.value.slave_id
    }
    if (pointForm.value.scale !== null) {
      config.scale = pointForm.value.scale
    }
    if (pointForm.value.offset !== null) {
      config.offset = pointForm.value.offset
    }
    if (pointForm.value.byte_order !== 'big') {
      config.byte_order = pointForm.value.byte_order
    }
    if (pointForm.value.word_order !== 'big') {
      config.word_order = pointForm.value.word_order
    }
  } else if (pluginName === 'knx') {
    config.group_address = pointForm.value.group_address
    if (pointForm.value.status_address) {
      config.status_address = pointForm.value.status_address
    }
    if (pointForm.value.control_address) {
      config.control_address = pointForm.value.control_address
    }
    if (pointForm.value.writable) {
      config.writable = true
    }
    if (pointForm.value.scale !== null) {
      config.scale = pointForm.value.scale
    }
    if (pointForm.value.offset !== null) {
      config.offset = pointForm.value.offset
    }
  } else if (pluginName === 'bacnet') {
    config.object_type = pointForm.value.object_type
    config.object_instance = pointForm.value.object_instance
    if (pointForm.value.property !== 'presentValue') {
      config.property = pointForm.value.property
    }
    if (pointForm.value.scale !== null) {
      config.scale = pointForm.value.scale
    }
    if (pointForm.value.offset !== null) {
      config.offset = pointForm.value.offset
    }
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
        standard_data_type: pointForm.value.standard_data_type || undefined,
        unit: pointForm.value.unit,
        enabled: pointForm.value.enabled,
        config,
        metadata,
        tags: pointForm.value.tags ? pointForm.value.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      }
      await pointStore.updatePoint(asset, editingPointName.value, updates)
      ElMessage.success('点位已更新')
    } else {
      const point: PointConfig = {
        name: pointForm.value.name,
        description: pointForm.value.description || undefined,
        data_type: pointForm.value.data_type,
        standard_data_type: (pointForm.value.standard_data_type || undefined) as StandardDataType | undefined,
        unit: pointForm.value.unit || undefined,
        enabled: pointForm.value.enabled,
        config,
        metadata,
        tags: pointForm.value.tags ? pointForm.value.tags.split(',').map(t => t.trim()).filter(Boolean) : []
      }
      await pointStore.addPoint(asset, point)
      ElMessage.success('点位已添加')
    }
    showPointDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : '未知错误')
    ElMessage.error(isEditingPoint.value ? '更新点位失败: ' + detail : '添加点位失败: ' + detail)
  } finally {
    savingPoint.value = false
  }
}

const handleDeletePoint = (pointName: string) => {
  if (!selectedDeviceAsset.value) return
  ElMessageBox.confirm(
    `确定要删除点位 "${pointName}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await pointStore.removePoint(selectedDeviceAsset.value!, pointName)
      ElMessage.success('点位已删除')
    } catch (e: unknown) {
      ElMessage.error('删除失败: ' + (e instanceof Error ? e.message : '未知错误'))
    }
  }).catch(() => {})
}

onMounted(async () => {
  await deviceStore.fetchDevices()
  await pointStore.fetchDevicesWithPoints()
})
</script>

<template>
  <div class="devices-page">
    <div class="page-header">
      <h2>设备管理</h2>
    </div>
    
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索设备..."
          :prefix-icon="Search"
          clearable
          style="width: 250px"
          @input="handleSearch"
        />
        <el-select 
          v-model="statusFilter" 
          placeholder="状态筛选" 
          clearable
          style="width: 120px"
          @change="handleFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" @click="handleAddDevice">
          新增设备
        </el-button>
        <el-button :icon="Refresh" @click="handleRefresh" :loading="deviceStore.loading">
          刷新
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
    
    <div class="main-content">
      <div class="device-list-panel">
        <div class="panel-header">
          <span class="panel-title">设备列表</span>
          <span class="device-count">{{ filteredSouthDevices.length }} 个设备</span>
        </div>
        
        <div v-if="deviceStore.loading && deviceStore.southDevices.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>加载设备列表...</p>
        </div>

        <div v-else-if="filteredSouthDevices.length === 0" class="empty-state">
          <p>暂无设备</p>
        </div>

        <div v-else class="device-list">
          <div 
            v-for="device in filteredSouthDevices" 
            :key="device.asset" 
            class="device-item"
            :class="{ 
              offline: !device.enabled || device.status !== 'active',
              selected: selectedDeviceAsset === device.asset 
            }"
            @click="handleViewPoints(device.asset)"
          >
            <div class="device-item-status" :class="{ online: device.enabled && device.status === 'active' }">
              <el-icon v-if="device.enabled && device.status === 'active'"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
            <div class="device-item-content">
              <div class="device-item-header">
                <span class="device-item-name">{{ device.name }}</span>
                <el-tag size="small" :type="getStatusType(device.status, device.enabled)">
                  {{ getStatusLabel(device.status, device.enabled) }}
                </el-tag>
              </div>
              <div class="device-item-meta">
                <span>{{ device.pluginName }}</span>
                <span>{{ device.pointCount }} 点位</span>
              </div>
            </div>
            <div class="device-item-actions" @click.stop>
              <el-switch 
                :model-value="device.enabled" 
                size="small"
                @change="handleToggleDevice(device.asset)"
              />
            </div>
          </div>
        </div>
      </div>
      
      <div class="points-panel">
        <div v-if="!selectedDeviceAsset" class="empty-points">
          <el-icon :size="48"><TrendCharts /></el-icon>
          <p>请从左侧选择一个设备查看点位列表</p>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <span class="panel-title">{{ deviceStore.getDeviceByAsset(selectedDeviceAsset)?.name || selectedDeviceAsset }} 点位列表</span>
            <div class="points-actions">
              <el-button type="primary" :icon="Plus" size="small" @click="handleAddPoint">
                新增点位
              </el-button>
            </div>
          </div>
          
          <el-table 
            :data="getDevicePoints(selectedDeviceAsset)" 
            stripe 
            style="width: 100%; flex: 1;"
            height="100%"
          >
            <el-table-column prop="name" label="点位名称" width="150" />
            <el-table-column prop="description" label="描述" width="150" />
            <el-table-column label="当前值" width="120">
              <template #default="{ row }">
                <span v-if="row.currentValue !== undefined && row.currentValue !== null" class="current-value">
                  {{ row.currentValue }}{{ row.unit ? ' ' + row.unit : '' }}
                </span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="数据类型" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.data_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="质量" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.quality" size="small" :type="row.quality === 'good' ? 'success' : row.quality === 'bad' ? 'danger' : 'warning'">
                  {{ row.quality === 'good' ? '良好' : row.quality === 'bad' ? '异常' : '不确定' }}
                </el-tag>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="更新时间" width="170">
              <template #default="{ row }">
                <span v-if="row.lastUpdate">{{ row.lastUpdate }}</span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="配置" min-width="150">
              <template #default="{ row }">
                <span class="config-preview">{{ JSON.stringify(row.config) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewTrend(selectedDeviceAsset!, row.name)">
                  趋势
                </el-button>
                <el-button type="primary" link size="small" @click="handleEditPoint(row)">
                  编辑
                </el-button>
                <el-button type="danger" link size="small" @click="handleDeletePoint(row.name)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </div>
    
    <el-dialog 
      v-model="showDeviceDialog" 
      :title="isEditing ? '编辑设备' : '新增设备'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceFormRules" label-width="100px">
        <el-form-item label="资产标识" prop="asset">
          <el-input 
            v-model="deviceForm.asset" 
            placeholder="仅允许字母、数字、下划线、连字符"
            :disabled="isEditing"
          />
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model="deviceForm.name" placeholder="请输入设备名称（留空则使用资产标识）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="deviceForm.description" type="textarea" :rows="2" placeholder="请输入设备描述" />
        </el-form-item>
        <el-form-item label="协议类型" prop="pluginName">
          <el-select v-model="deviceForm.pluginName" placeholder="请选择协议" @change="handlePluginChange">
            <el-option 
              v-for="opt in pluginOptions" 
              :key="opt.value" 
              :label="opt.label" 
              :value="opt.value" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址" prop="host">
          <el-input v-model="deviceForm.host" placeholder="请输入主机地址，如 192.168.1.100" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="deviceForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'modbus_tcp' || deviceForm.pluginName === 'modbus_rtu'" label="从站ID">
          <el-input-number v-model="deviceForm.slave_id" :min="0" :max="255" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'bacnet'" label="设备ID">
          <el-input-number v-model="deviceForm.device_id" :min="0" :max="4194303" />
        </el-form-item>
        <el-form-item v-if="deviceForm.pluginName === 'knx'" label="本地IP">
          <el-input v-model="deviceForm.local_ip" placeholder="可选，本地IP地址" />
        </el-form-item>
        <el-form-item label="超时(秒)">
          <el-input-number v-model="deviceForm.timeout" :min="1" :max="60" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="deviceForm.enabled" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="deviceForm.tags" placeholder="多个标签用逗号分隔，如: 厂房1,温度" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeviceDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog 
      v-model="showPointDialog" 
      :title="isEditingPoint ? '编辑点位' : '新增点位'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form ref="pointFormRef" :model="pointForm" :rules="pointFormRules" label-width="100px">
        <el-form-item label="点位名称" prop="name">
          <el-input 
            v-model="pointForm.name" 
            placeholder="仅允许字母、数字、下划线、连字符、中文"
            :disabled="isEditingPoint"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="pointForm.description" placeholder="请输入点位描述" />
        </el-form-item>
        
        <el-divider content-position="left">协议配置</el-divider>
        
        <template v-if="currentDevicePluginName === 'modbus_tcp' || currentDevicePluginName === 'modbus_rtu'">
          <el-form-item label="数据类型" prop="data_type">
            <el-select v-model="pointForm.data_type" placeholder="请选择数据类型">
              <el-option 
                v-for="opt in modbusDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="寄存器地址" prop="address">
            <el-input-number v-model="pointForm.address" :min="0" :max="65535" placeholder="Modbus寄存器地址" />
          </el-form-item>
          <el-form-item label="寄存器类型">
            <el-select v-model="pointForm.register_type" placeholder="请选择寄存器类型">
              <el-option 
                v-for="opt in registerTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="寄存器数量">
            <el-input-number v-model="pointForm.count" :min="1" :max="16" placeholder="多字节数据类型需要多个寄存器" />
          </el-form-item>
          <el-form-item label="从站ID">
            <el-input-number v-model="pointForm.slave_id" :min="0" :max="255" placeholder="可选，覆盖设备级别配置" clearable />
          </el-form-item>
          <el-form-item label="缩放因子">
            <el-input-number v-model="pointForm.scale" placeholder="可选，如 0.1" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item label="偏移量">
            <el-input-number v-model="pointForm.offset" placeholder="可选，如 -273.15" :precision="4" clearable />
          </el-form-item>
          <el-form-item label="字节顺序">
            <el-radio-group v-model="pointForm.byte_order">
              <el-radio value="big">大端 (Big)</el-radio>
              <el-radio value="little">小端 (Little)</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="字顺序">
            <el-radio-group v-model="pointForm.word_order">
              <el-radio value="big">大端 (Big)</el-radio>
              <el-radio value="little">小端 (Little，西门子/三菱)</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>
        
        <template v-else-if="currentDevicePluginName === 'knx'">
          <el-form-item label="数据类型" prop="data_type">
            <el-select v-model="pointForm.data_type" placeholder="请选择数据类型">
              <el-option 
                v-for="opt in knxDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="组地址" prop="group_address">
            <el-input v-model="pointForm.group_address" placeholder="KNX组地址，如 1/2/3" />
          </el-form-item>
          <el-form-item label="状态地址">
            <el-input v-model="pointForm.status_address" placeholder="可选，状态组地址" />
          </el-form-item>
          <el-form-item label="控制地址">
            <el-input v-model="pointForm.control_address" placeholder="可选，控制组地址" />
          </el-form-item>
          <el-form-item label="可写">
            <el-switch v-model="pointForm.writable" />
          </el-form-item>
          <el-form-item label="缩放因子">
            <el-input-number v-model="pointForm.scale" placeholder="可选" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item label="偏移量">
            <el-input-number v-model="pointForm.offset" placeholder="可选" :precision="4" clearable />
          </el-form-item>
        </template>
        
        <template v-else-if="currentDevicePluginName === 'bacnet'">
          <el-form-item label="对象类型" prop="object_type">
            <el-select v-model="pointForm.object_type" placeholder="请选择对象类型" @change="pointForm.data_type = pointForm.object_type">
              <el-option 
                v-for="opt in bacnetDataTypes" 
                :key="opt.value" 
                :label="opt.label" 
                :value="opt.value" 
              />
            </el-select>
          </el-form-item>
          <el-form-item label="对象实例" prop="object_instance">
            <el-input-number v-model="pointForm.object_instance" :min="0" placeholder="BACnet对象实例ID" />
          </el-form-item>
          <el-form-item label="属性">
            <el-input v-model="pointForm.property" placeholder="默认为 presentValue" />
          </el-form-item>
          <el-form-item label="缩放因子">
            <el-input-number v-model="pointForm.scale" placeholder="可选" :precision="4" :step="0.1" clearable />
          </el-form-item>
          <el-form-item label="偏移量">
            <el-input-number v-model="pointForm.offset" placeholder="可选" :precision="4" clearable />
          </el-form-item>
        </template>
        
        <template v-else>
          <el-form-item label="数据类型" prop="data_type">
            <el-input v-model="pointForm.data_type" placeholder="协议特定类型" />
          </el-form-item>
          <el-form-item label="协议配置">
            <el-input 
              v-model="pointForm.configJson" 
              type="textarea" 
              :rows="4" 
              placeholder='JSON格式的协议配置'
            />
          </el-form-item>
        </template>
        
        <el-divider content-position="left">通用配置</el-divider>
        
        <el-form-item label="标准类型">
          <el-select v-model="pointForm.standard_data_type" placeholder="可选，由插件自动推导" clearable>
            <el-option label="布尔 (bool)" value="bool" />
            <el-option label="整数 (int)" value="int" />
            <el-option label="浮点 (float)" value="float" />
            <el-option label="字符串 (string)" value="string" />
          </el-select>
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="pointForm.unit" placeholder="如 °C, %, V, A" />
        </el-form-item>
        
        <el-divider content-position="left">元数据 (可选)</el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小值">
              <el-input-number v-model="pointForm.min" placeholder="可选" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大值">
              <el-input-number v-model="pointForm.max" placeholder="可选" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="高报警">
              <el-input-number v-model="pointForm.alarm_high" placeholder="可选" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="低报警">
              <el-input-number v-model="pointForm.alarm_low" placeholder="可选" clearable style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="启用">
          <el-switch v-model="pointForm.enabled" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="pointForm.tags" placeholder="多个标签用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPointDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSavePoint" :loading="savingPoint">保存</el-button>
      </template>
    </el-dialog>
    
    <el-drawer
      v-model="showTrend"
      title="点位趋势"
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
  </div>
</template>

<style scoped>
.devices-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #2c3e50;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  gap: 12px;
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

.device-list-panel {
  width: 320px;
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

@media (max-width: 900px) {
  .main-content {
    flex-direction: column;
  }
  
  .device-list-panel {
    width: 100%;
    max-height: 300px;
  }
  
  .points-panel {
    min-height: 400px;
  }
}
</style>
