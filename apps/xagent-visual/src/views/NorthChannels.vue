<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useChannelStore } from '@/stores/channels'
import { useUserStore } from '@/stores/users'
import { channelApi } from '@/api/channels'
import type { NorthChannelConfig, NorthChannelProtocol } from '@/api/types'
import type { ChannelListItem } from '@/stores/channels'
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
  Connection,
  Delete,
  Edit,
  MoreFilled,
  RefreshRight
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// XNC映射配置模板
const XNC_MAPPING_TEMPLATE = {
  "vdid_mapping": {
    "device_1": 1,
    "device_2": 2
  },
  "oid_mapping": {
    "device_1.temperature": 1,
    "device_1.humidity": 2,
    "device_2.pressure": 3
  },
  "pid": {
    "point_value": 85,
    "point_error": 103
  }
}

const channelStore = useChannelStore()
const userStore = useUserStore()
const { isTouch, isTablet, isMobile, width } = useResponsive()

const searchQuery = ref('')
const statusFilter = ref('')
const protocolFilter = ref('')
const selectedChannelId = ref<string | null>(null)

const activeTab = ref('channels')

const isCompactMode = computed(() => isTablet.value || isMobile.value || width.value <= 1024)

const filteredChannels = computed(() => {
  let list = channelStore.channelList
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    list = list.filter(c =>
      c.name.toLowerCase().includes(query) ||
      c.id.toLowerCase().includes(query) ||
      c.protocol.toLowerCase().includes(query)
    )
  }
  if (statusFilter.value === 'online') {
    list = list.filter(c => c.connectionStatus === 'online')
  } else if (statusFilter.value === 'offline') {
    list = list.filter(c => c.connectionStatus !== 'online')
  }
  if (protocolFilter.value) {
    list = list.filter(c => c.protocol === protocolFilter.value)
  }
  return list
})

const handleSearch = () => {}

const handleFilterChange = () => {}

const handleToggleChannel = async (id: string) => {
  try {
    await channelStore.toggleChannel(id)
    ElMessage.success('通道状态已切换')
  } catch (e: unknown) {
    ElMessage.error('操作失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

const handleRefresh = async () => {
  await channelStore.fetchChannels()
}

const showChannelDialog = ref(false)
const channelForm = ref({
  id: '',
  name: '',
  description: '',
  enabled: true,
  protocol: 'mqtt' as NorthChannelProtocol,
  host: '',
  port: 1883,
  username: '',
  password: '',
  client_id: '',
  topic: '',
  qos: 0 as 0 | 1 | 2,
  keepalive: 60,
  clean_session: true,
  adapter: 'standard',
  adapter_config: '{}',
  command_topic: '',
  publish_mode: 'single' as 'single' | 'batch',
  command_timeout: 30,
  local_port: 8888,
  remote_host: '127.0.0.1',
  remote_port: 9000,
  reconnect_interval: 5,
  mapping_config: '{}',
  endpoint: '',
  method: 'POST' as 'GET' | 'POST' | 'PUT',
  headers: '{}',
  timeout: 30,
  immediate_upload: true,
  batch_size: 100,
  interval: 5,
  retry_times: 3,
  retry_interval: 5,
  tags: ''
})
const channelFormRef = ref()
const isEditing = ref(false)
const editingId = ref('')
const saving = ref(false)

const protocolOptions = [
  { 
    label: 'MQTT', 
    value: 'mqtt', 
    defaultPort: 1883,
    defaultConfig: {
      client_id: `xagent_${Date.now()}`,
      topic: 'data/upload',
      qos: 1,
      keepalive: 60,
      clean_session: true,
      command_topic: 'xagent/command',
      publish_mode: 'single',
      command_timeout: 30
    }
  },
  { 
    label: 'XNC', 
    value: 'xnc', 
    defaultPort: 9000,
    defaultConfig: { 
      local_port: 8888,
      remote_host: '127.0.0.1',
      remote_port: 9000,
      reconnect_interval: 5
    }
  },
  { 
    label: 'HTTP', 
    value: 'http', 
    defaultPort: 80,
    defaultConfig: { 
      method: 'POST',
      timeout: 30
    }
  }
]

const mqttAdapterOptions = [
  { label: '标准适配器', value: 'standard', description: '默认数据格式' },
  { label: '客户A (C001)', value: 'C001', description: '客户A私有云协议' },
]

// 适配器默认配置缓存（从后端API获取）
const adapterDefaultsCache = ref<Record<string, any>>({})

// 产品Key（独立存储，便于表单绑定）
const productKey = ref('')

// 获取适配器默认配置
const loadAdapterDefaults = async (adapterCode: string): Promise<any> => {
  // 如果已缓存，直接返回
  if (adapterDefaultsCache.value[adapterCode]) {
    return adapterDefaultsCache.value[adapterCode]
  }

  try {
    const result = await channelApi.getAdapterDefaults(adapterCode)
    adapterDefaultsCache.value[adapterCode] = result.defaults
    return result.defaults
  } catch (e) {
    console.error('Failed to load adapter defaults:', e)
    return null
  }
}

// 同步 productKey 到 adapter_config
watch(productKey, (newVal) => {
  if (channelForm.value.adapter === 'C001') {
    try {
      const config = JSON.parse(channelForm.value.adapter_config || '{}')
      config.productKey = newVal
      channelForm.value.adapter_config = JSON.stringify(config, null, 2)
    } catch {
      // ignore
    }
  }
})

// 适配器变更处理
const handleAdapterChange = async (adapter: string) => {
  if (adapter === 'standard') {
    channelForm.value.adapter_config = '{}'
    productKey.value = ''
  } else {
    // 仅在新增或配置为空时预填充，避免编辑时覆盖已有配置
    if (!isEditing.value || !channelForm.value.adapter_config || channelForm.value.adapter_config === '{}') {
      // 从后端API获取默认配置
      const defaults = await loadAdapterDefaults(adapter)
      if (defaults) {
        channelForm.value.adapter_config = JSON.stringify(defaults, null, 2)
        // 同步 productKey
        productKey.value = defaults.productKey || ''
      }
    }
  }
}

// 填充XNC映射配置模板
const fillMappingTemplate = () => {
  channelForm.value.mapping_config = JSON.stringify(XNC_MAPPING_TEMPLATE, null, 2)
}

const channelFormRules = {
  id: [{ required: true, message: '请输入通道ID', trigger: 'blur' }],
  name: [{ required: true, message: '请输入通道名称', trigger: 'blur' }],
  protocol: [{ required: true, message: '请选择协议类型', trigger: 'change' }]
}

const handleProtocolChange = (val: NorthChannelProtocol) => {
  const opt = protocolOptions.find(o => o.value === val)
  if (opt) {
    channelForm.value.port = opt.defaultPort
    if (opt.defaultConfig) {
      Object.assign(channelForm.value, opt.defaultConfig)
    }
  }
}

const handleAddChannel = () => {
  isEditing.value = false
  editingId.value = ''
  productKey.value = ''  // 重置产品Key
  channelForm.value = {
    id: '',
    name: '',
    description: '',
    enabled: true,
    protocol: 'mqtt',
    host: '',
    port: 1883,
    username: '',
    password: '',
    client_id: `xagent_${Date.now()}`,
    topic: 'data/upload',
    qos: 1,
    keepalive: 60,
    clean_session: true,
    adapter: 'standard',
    adapter_config: '{}',
    command_topic: '',
    publish_mode: 'single',
    command_timeout: 30,
    local_port: 8888,
    remote_host: '127.0.0.1',
    remote_port: 9000,
    reconnect_interval: 5,
    mapping_config: '{}',
    endpoint: '',
    method: 'POST',
    headers: '{}',
    timeout: 30,
    immediate_upload: true,
    batch_size: 100,
    interval: 5,
    retry_times: 3,
    retry_interval: 5,
    tags: ''
  }
  showChannelDialog.value = true
}

const handleEditChannel = (channel: ChannelListItem) => {
  const fullChannel = channelStore.getChannelById(channel.id)
  if (!fullChannel) return
  
  isEditing.value = true
  editingId.value = channel.id
  channelForm.value = {
    id: channel.id,
    name: channel.name,
    description: fullChannel.description || '',
    enabled: channel.enabled,
    protocol: channel.protocol,
    host: fullChannel.connection.broker || fullChannel.connection.remote_host || '',
    port: fullChannel.connection.port || fullChannel.connection.remote_port || 1883,
    username: fullChannel.connection.username || '',
    password: '',
    client_id: fullChannel.connection.client_id || '',
    topic: fullChannel.connection.topic || '',
    qos: fullChannel.connection.qos || 0,
    keepalive: fullChannel.connection.keepalive || 60,
    clean_session: fullChannel.connection.clean_session ?? true,
    adapter: fullChannel.adapter.adapter || 'standard',
    adapter_config: JSON.stringify(fullChannel.adapter.config || {}, null, 2),
    command_topic: fullChannel.connection.command_topic || '',
    publish_mode: fullChannel.connection.publish_mode || 'single',
    command_timeout: fullChannel.connection.command_timeout || 30,
    local_port: fullChannel.connection.local_port || 8888,
    remote_host: fullChannel.connection.remote_host || '127.0.0.1',
    remote_port: fullChannel.connection.remote_port || 9000,
    reconnect_interval: fullChannel.connection.reconnect_interval || 5,
    mapping_config: JSON.stringify(fullChannel.adapter.mapping_config || {}, null, 2),
    endpoint: fullChannel.connection.endpoint || '',
    method: fullChannel.connection.method || 'POST',
    headers: JSON.stringify(fullChannel.adapter.headers || {}, null, 2),
    timeout: fullChannel.connection.timeout || 30,
    immediate_upload: fullChannel.upload_strategy.immediate_upload,
    batch_size: fullChannel.upload_strategy.batch_size,
    interval: fullChannel.upload_strategy.interval,
    retry_times: fullChannel.upload_strategy.retry_times,
    retry_interval: fullChannel.upload_strategy.retry_interval || 5,
    tags: (fullChannel.tags || []).join(', ')
  }
  
  // 从 adapter_config 中提取 productKey
  try {
    const config = JSON.parse(channelForm.value.adapter_config || '{}')
    productKey.value = config.productKey || ''
  } catch {
    productKey.value = ''
  }
  
  showChannelDialog.value = true
}

const buildChannelConfig = (): NorthChannelConfig => {
  const connection: any = {}
  let adapterConfig: any = {}
  let adapterType = 'default'
  
  // 根据协议类型构建扁平的连接配置
  if (channelForm.value.protocol === 'mqtt') {
    // MQTT协议配置
    connection.broker = channelForm.value.host
    connection.port = channelForm.value.port
    if (channelForm.value.username) connection.username = channelForm.value.username
    if (channelForm.value.password) connection.password = channelForm.value.password
    connection.client_id = channelForm.value.client_id
    connection.topic = channelForm.value.topic
    connection.qos = channelForm.value.qos
    connection.keepalive = channelForm.value.keepalive
    connection.clean_session = channelForm.value.clean_session
    if (channelForm.value.command_topic) connection.command_topic = channelForm.value.command_topic
    if (channelForm.value.publish_mode) connection.publish_mode = channelForm.value.publish_mode
    if (channelForm.value.command_timeout) connection.command_timeout = channelForm.value.command_timeout
    
    adapterType = 'mqtt'
    
    // 适配器配置
    if (channelForm.value.adapter) {
      adapterConfig.adapter = channelForm.value.adapter
    }
    try {
      const adapterConfigObj = JSON.parse(channelForm.value.adapter_config)
      if (Object.keys(adapterConfigObj).length > 0) {
        adapterConfig.config = adapterConfigObj
      }
    } catch (e) {
      console.error('Invalid adapter config JSON:', e)
    }
  } else if (channelForm.value.protocol === 'xnc') {
    connection.local_port = channelForm.value.local_port
    connection.remote_host = channelForm.value.remote_host
    connection.remote_port = channelForm.value.remote_port
    connection.reconnect_interval = channelForm.value.reconnect_interval
    
    adapterType = 'xnc_protobuf'
    
    try {
      const mappingConfig = JSON.parse(channelForm.value.mapping_config)
      if (Object.keys(mappingConfig).length > 0) {
        adapterConfig.mapping_config = mappingConfig
      }
    } catch (e) {
      console.error('Invalid mapping config JSON:', e)
    }
  } else if (channelForm.value.protocol === 'http') {
    // HTTP协议配置
    connection.endpoint = channelForm.value.endpoint
    connection.method = channelForm.value.method
    connection.timeout = channelForm.value.timeout
    if (channelForm.value.username) connection.username = channelForm.value.username
    if (channelForm.value.password) connection.password = channelForm.value.password
    
    adapterType = 'http'
    
    // 添加 headers 到 adapter.config
    try {
      const headers = JSON.parse(channelForm.value.headers)
      if (Object.keys(headers).length > 0) {
        adapterConfig.headers = headers
      }
    } catch (e) {
      console.error('Invalid headers JSON:', e)
    }
  }
  
  const config: any = {
    id: channelForm.value.id,
    name: channelForm.value.name,
    enabled: channelForm.value.enabled,
    protocol: channelForm.value.protocol,
    connection,
    adapter: {
      type: adapterType,
      ...adapterConfig
    },
    upload_strategy: {
      immediate_upload: channelForm.value.immediate_upload,
      batch_size: channelForm.value.batch_size,
      interval: channelForm.value.interval,
      retry_times: channelForm.value.retry_times,
      retry_interval: channelForm.value.retry_interval
    }
  }
  
  if (channelForm.value.description) {
    config.description = channelForm.value.description
  }
  
  if (channelForm.value.tags) {
    config.tags = channelForm.value.tags.split(',').map(t => t.trim()).filter(Boolean)
  }
  
  return config
}

const handleSaveChannel = async () => {
  if (!channelFormRef.value) return
  try {
    await channelFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const config = buildChannelConfig()
    
    if (isEditing.value) {
      await channelStore.updateChannel(editingId.value, config)
      ElMessage.success('通道已更新')
    } else {
      await channelStore.createChannel(config)
      ElMessage.success('通道已创建')
    }
    showChannelDialog.value = false
  } catch (e: unknown) {
    const detail = (e as any)?.response?.data?.detail || (e instanceof Error ? e.message : '未知错误')
    ElMessage.error(isEditing.value ? '更新失败: ' + detail : '创建失败: ' + detail)
  } finally {
    saving.value = false
  }
}

const handleDeleteChannel = (channel: ChannelListItem) => {
  ElMessageBox.confirm(
    `确定要删除通道 "${channel.name}" (${channel.id}) 吗？此操作不可恢复。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await channelStore.deleteChannel(channel.id)
      if (selectedChannelId.value === channel.id) {
        selectedChannelId.value = null
      }
      ElMessage.success('通道已删除')
    } catch (e: unknown) {
      ElMessage.error('删除失败: ' + (e instanceof Error ? e.message : '未知错误'))
    }
  }).catch(() => {})
}

const handleTestConnection = async (id: string) => {
  try {
    ElMessage.info('正在测试连接...')
    const result = await channelStore.testConnection(id)
    if (result.success) {
      ElMessage.success(`连接成功！延迟: ${result.latency}ms`)
    } else {
      ElMessage.error('连接失败: ' + result.message)
    }
  } catch (e: unknown) {
    ElMessage.error('测试失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

const handleRestartChannel = async (id: string) => {
  try {
    await channelStore.restartChannel(id)
    ElMessage.success('通道已重启')
  } catch (e: unknown) {
    ElMessage.error('重启失败: ' + (e instanceof Error ? e.message : '未知错误'))
  }
}

const handleViewDetails = (id: string) => {
  selectedChannelId.value = id
}

const handleExportYaml = async () => {
  try {
    console.log('开始导出通道...')
    const result = await channelApi.exportChannels()
    console.log('导出结果:', result)
    
    const channels = result.channels || []
    
    if (channels.length === 0) {
      ElMessage.warning('没有可导出的通道')
      return
    }
    
    const content = yaml.dump({ channels }, { 
      indent: 2, 
      lineWidth: 120,
      noRefs: true,
      sortKeys: false
    })
    const blob = new Blob([content], { type: 'text/yaml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `xagent-channels-${new Date().toISOString().slice(0, 10)}.yaml`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${channels.length} 个通道`)
  } catch (e: unknown) {
    console.error('导出失败:', e)
    if (e instanceof Error) {
      console.error('错误详情:', e.message)
      console.error('错误堆栈:', e.stack)
    }
    const errorMsg = e instanceof Error ? e.message : '未知错误'
    ElMessage.error(`导出失败: ${errorMsg}`)
  }
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
    const parsed = yaml.load(text) as { channels?: NorthChannelConfig[] }
    if (!parsed.channels || !Array.isArray(parsed.channels)) {
      ElMessage.error('无效的 YAML 文件：缺少 channels 数组')
      return
    }

    const channels = parsed.channels
    await ElMessageBox.confirm(
      `即将导入 ${channels.length} 个通道，是否继续？`,
      '导入确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )

    const result = await channelApi.importChannels({ channels: parsed.channels }, false)
    if (result.failed > 0) {
      ElMessage.warning(`导入完成：成功 ${result.succeeded}，失败 ${result.failed}`)
    } else {
      ElMessage.success(`成功导入 ${result.succeeded} 个通道`)
    }
    await channelStore.fetchChannels()
  } catch (e: unknown) {
    if ((e as any) !== 'cancel') {
      ElMessage.error('导入失败: ' + (e instanceof Error ? e.message : '未知错误'))
    }
  }
}

const selectedChannel = computed(() => {
  if (!selectedChannelId.value) return null
  return channelStore.getChannelById(selectedChannelId.value)
})

// 格式化数字（添加千分位）
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toLocaleString()
}

onMounted(async () => {
  await channelStore.fetchChannels()
})
</script>

<template>
  <div class="channels-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索通道..."
          :prefix-icon="Search"
          clearable
          class="toolbar-search"
          @input="handleSearch"
        />
        <el-select 
          v-model="statusFilter" 
          placeholder="状态筛选" 
          clearable
          class="toolbar-filter"
          @change="handleFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
        </el-select>
        <el-select 
          v-model="protocolFilter" 
          placeholder="协议筛选" 
          clearable
          class="toolbar-filter"
          @change="handleFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="MQTT" value="mqtt" />
          <el-option label="XNC" value="xnc" />
          <el-option label="HTTP" value="http" />
        </el-select>
        <div class="toolbar-stats">
          <span class="stat-item">
            <span class="stat-value">{{ channelStore.totalChannels }}</span>
            <span class="stat-label">通道</span>
          </span>
          <span class="stat-divider">/</span>
          <span class="stat-item stat-online">
            <span class="stat-value">{{ channelStore.onlineChannels }}</span>
            <span class="stat-label">在线</span>
          </span>
        </div>
      </div>
      <div class="toolbar-right">
        <el-button v-if="userStore.hasPermission('devices', 'create')" type="primary" :icon="Plus" @click="handleAddChannel">
          新增通道
        </el-button>
        <el-button :icon="Download" @click="handleExportYaml">
          导出
        </el-button>
        <el-button v-if="userStore.hasPermission('devices', 'create')" :icon="Upload" @click="handleImportYaml">
          导入
        </el-button>
        <el-button :icon="Refresh" @click="handleRefresh" :loading="channelStore.loading">
          刷新
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="channelStore.error"
      :title="channelStore.error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 16px"
    />
    
    <div v-if="isCompactMode" class="main-content compact-mode">
      <div class="compact-tabs">
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'channels' }"
          @click="activeTab = 'channels'"
        >
          通道列表
          <span v-if="selectedChannelId" class="tab-badge">{{ selectedChannel?.name }}</span>
        </div>
        <div 
          class="compact-tab" 
          :class="{ active: activeTab === 'details', disabled: !selectedChannelId }"
          @click="selectedChannelId && (activeTab = 'details')"
        >
          通道详情
        </div>
      </div>
      
      <div v-show="activeTab === 'channels'" class="compact-panel channel-panel">
        <div v-if="channelStore.loading && channelStore.channels.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>加载通道列表...</p>
        </div>

        <div v-else-if="filteredChannels.length === 0" class="empty-state">
          <p>暂无通道</p>
        </div>

        <div v-else class="channel-grid">
          <div 
            v-for="channel in filteredChannels" 
            :key="channel.id" 
            class="channel-card-compact"
            :class="{ 
              offline: channel.connectionStatus !== 'online',
              selected: selectedChannelId === channel.id 
            }"
            @click="handleViewDetails(channel.id); activeTab = 'details'"
          >
            <div class="channel-card-header">
              <div class="channel-card-status" :class="{ online: channel.connectionStatus === 'online' }">
                <el-icon v-if="channel.connectionStatus === 'online'"><CircleCheck /></el-icon>
                <el-icon v-else><CircleClose /></el-icon>
              </div>
              <div class="channel-card-info">
                <div class="channel-card-name">{{ channel.name }}</div>
                <div class="channel-card-meta">
                  <span>{{ channel.protocol.toUpperCase() }}</span>
                  <span>{{ channel.uploadRate }} 条/分</span>
                </div>
              </div>
            </div>
            <div class="channel-card-stats">
              <div class="stat-mini">
                <span class="stat-mini-label">成功率</span>
                <span class="stat-mini-value">{{ channel.successRate }}%</span>
              </div>
              <div class="stat-mini">
                <span class="stat-mini-label">积压</span>
                <span class="stat-mini-value">{{ channel.backlogCount }}</span>
              </div>
            </div>
            <div class="channel-card-actions">
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="channel.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleChannel(channel.id)"
                @click.stop
              />
              <div class="action-buttons" @click.stop>
                <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" link :size="isTouch ? 'default' : 'small'" @click="handleEditChannel(channel)">
                  编辑
                </el-button>
                <el-button v-if="userStore.hasPermission('devices', 'delete')" type="danger" link :size="isTouch ? 'default' : 'small'" @click="handleDeleteChannel(channel)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div v-show="activeTab === 'details'" class="compact-panel details-panel">
        <div v-if="!selectedChannelId" class="empty-details">
          <el-icon :size="48"><Connection /></el-icon>
          <p>请先选择一个通道</p>
          <el-button type="primary" @click="activeTab = 'channels'">返回通道列表</el-button>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <div class="panel-header-left">
              <el-button link @click="activeTab = 'channels'">
                <el-icon><RefreshRight /></el-icon>
                返回通道
              </el-button>
            </div>
            <span class="panel-title">{{ selectedChannel?.name }}</span>
            <div class="header-info">
              <span class="status-dot" :class="{ online: selectedChannel?.status === 'online' }"></span>
              <span class="protocol-tag">{{ selectedChannel?.protocol?.toUpperCase() }}</span>
            </div>
            <div class="header-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" plain @click="handleTestConnection(selectedChannelId!)">
                测试
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" plain @click="handleRestartChannel(selectedChannelId!)">
                重启
              </el-button>
            </div>
          </div>

          <div v-if="selectedChannel" class="channel-details-content">
            <!-- 统计仪表盘 -->
            <div v-if="selectedChannel.statistics" class="stats-dashboard">
              <div class="stat-item">
                <div class="stat-icon upload-icon">↑</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-label">条/分钟</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon success-icon">✓</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-label">成功率</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon backlog-icon">⏳</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-label">积压</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon total-icon">📊</div>
                <div class="stat-content">
                  <div class="stat-value">{{ formatNumber(selectedChannel.statistics.total_uploaded) }}</div>
                  <div class="stat-label">总上传</div>
                </div>
              </div>
            </div>

            <!-- 连接配置（合并基本信息） -->
            <div class="config-section">
              <div class="section-title">连接配置</div>
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-label">通道ID</span>
                  <span class="config-value">{{ selectedChannel.id }}</span>
                </div>
                <div class="config-item">
                  <span class="config-label">名称</span>
                  <span class="config-value">{{ selectedChannel.name }}</span>
                </div>
                <template v-if="selectedChannel.protocol === 'mqtt'">
                  <div class="config-item">
                    <span class="config-label">Broker</span>
                    <span class="config-value">{{ selectedChannel.connection.broker }}:{{ selectedChannel.connection.port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">客户端ID</span>
                    <span class="config-value code">{{ selectedChannel.connection.client_id }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">主题</span>
                    <span class="config-value code">{{ selectedChannel.connection.topic }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">QoS</span>
                    <span class="config-value">{{ selectedChannel.connection.qos }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">保活</span>
                    <span class="config-value">{{ selectedChannel.connection.keepalive }}秒</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">适配器</span>
                    <span class="config-value">
                      <el-tag v-if="selectedChannel.adapter.adapter" size="small" type="primary">{{ selectedChannel.adapter.adapter }}</el-tag>
                      <span v-else class="muted">标准</span>
                    </span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'xnc'">
                  <div class="config-item">
                    <span class="config-label">本地端口</span>
                    <span class="config-value">{{ selectedChannel.connection.local_port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">远程主机</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_host || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">远程端口</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_port || '--' }}</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'http'">
                  <div class="config-item full-width">
                    <span class="config-label">端点</span>
                    <span class="config-value code">{{ selectedChannel.connection.endpoint }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">方法</span>
                    <span class="config-value">{{ selectedChannel.connection.method }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">超时</span>
                    <span class="config-value">{{ selectedChannel.connection.timeout }}秒</span>
                  </div>
                </template>
              </div>
              <!-- 适配器配置JSON -->
              <div v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.adapter.config && Object.keys(selectedChannel.adapter.config).length > 0" class="adapter-config">
                <div class="adapter-config-title">适配器配置</div>
                <pre class="json-config">{{ JSON.stringify(selectedChannel.adapter.config, null, 2) }}</pre>
              </div>
            </div>

            <!-- 上传策略（可折叠） -->
            <el-collapse class="detail-collapse">
              <el-collapse-item title="上传策略">
                <div class="config-grid">
                  <div class="config-item">
                    <span class="config-label">立即上传</span>
                    <span class="config-value">
                      <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'" size="small">
                        {{ selectedChannel.upload_strategy.immediate_upload ? '是' : '否' }}
                      </el-tag>
                    </span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">批量大小</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.batch_size }} 条</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">上传间隔</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.interval }} 秒</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">重试次数</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.retry_times }} 次</span>
                  </div>
                </div>
              </el-collapse-item>
              <el-collapse-item v-if="selectedChannel.description" title="描述">
                <p class="description-text">{{ selectedChannel.description }}</p>
              </el-collapse-item>
            </el-collapse>
          </div>
        </template>
      </div>
    </div>
    
    <div v-else class="main-content">
      <div class="channel-list-panel">
        <div class="panel-header">
          <span class="panel-title">通道列表</span>
          <span class="channel-count">{{ filteredChannels.length }} 个通道</span>
        </div>
        
        <div v-if="channelStore.loading && channelStore.channels.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>加载通道列表...</p>
        </div>

        <div v-else-if="filteredChannels.length === 0" class="empty-state">
          <p>暂无通道</p>
        </div>

        <div v-else class="channel-list">
          <div 
            v-for="channel in filteredChannels" 
            :key="channel.id" 
            class="channel-item"
            :class="{ 
              offline: channel.connectionStatus !== 'online',
              selected: selectedChannelId === channel.id 
            }"
            @click="handleViewDetails(channel.id)"
          >
            <div class="channel-item-status" :class="{ online: channel.connectionStatus === 'online' }">
              <el-icon v-if="channel.connectionStatus === 'online'"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
            </div>
            <div class="channel-item-content">
              <div class="channel-item-header">
                <span class="channel-item-name">{{ channel.name }}</span>
              </div>
              <div class="channel-item-meta">
                <span>{{ channel.protocol.toUpperCase() }}</span>
                <span>{{ channel.uploadRate }} 条/分</span>
                <span>{{ channel.successRate }}%</span>
              </div>
            </div>
            <div class="channel-item-actions" @click.stop>
              <el-switch
                v-if="userStore.hasPermission('devices', 'update')"
                :model-value="channel.enabled" 
                :size="isTouch ? 'default' : 'small'"
                @change="handleToggleChannel(channel.id)"
              />
              <el-dropdown trigger="click" @command="(cmd: string) => {
                if (cmd === 'edit') handleEditChannel(channel)
                else if (cmd === 'test') handleTestConnection(channel.id)
                else if (cmd === 'restart') handleRestartChannel(channel.id)
                else if (cmd === 'delete') handleDeleteChannel(channel)
              }">
                <el-button type="info" link :size="isTouch ? 'default' : 'small'" class="more-btn">
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="edit" :icon="Edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="test" :icon="Connection">测试连接</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'update')" command="restart" :icon="RefreshRight">重启</el-dropdown-item>
                    <el-dropdown-item v-if="userStore.hasPermission('devices', 'delete')" command="delete" :icon="Delete" divided>
                      <span class="danger-text">删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </div>
      
      <div class="details-panel">
        <div v-if="!selectedChannelId" class="empty-details">
          <el-icon :size="48"><Connection /></el-icon>
          <p>请从左侧选择一个通道查看详情</p>
        </div>
        
        <template v-else>
          <div class="panel-header">
            <span class="panel-title">{{ selectedChannel?.name }}</span>
            <div class="header-info">
              <span class="status-dot" :class="{ online: selectedChannel?.status === 'online' }"></span>
              <span class="protocol-tag">{{ selectedChannel?.protocol?.toUpperCase() }}</span>
              <el-tag :type="selectedChannel?.enabled ? 'success' : 'info'" size="small">
                {{ selectedChannel?.enabled ? '已启用' : '已禁用' }}
              </el-tag>
            </div>
            <div class="header-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" plain @click="handleTestConnection(selectedChannelId!)">
                测试连接
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" plain @click="handleRestartChannel(selectedChannelId!)">
                重启
              </el-button>
            </div>
          </div>

          <div v-if="selectedChannel" class="channel-details-content">

            <!-- 统计仪表盘 -->
            <div v-if="selectedChannel.statistics" class="stats-dashboard">
              <div class="stat-item">
                <div class="stat-icon upload-icon">↑</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-label">条/分钟</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon success-icon">✓</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-label">成功率</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon backlog-icon">⏳</div>
                <div class="stat-content">
                  <div class="stat-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-label">积压</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon total-icon">📊</div>
                <div class="stat-content">
                  <div class="stat-value">{{ formatNumber(selectedChannel.statistics.total_uploaded) }}</div>
                  <div class="stat-label">总上传</div>
                </div>
              </div>
            </div>

            <!-- 连接配置（合并基本信息） -->
            <div class="config-section">
              <div class="section-title">连接配置</div>
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-label">通道ID</span>
                  <span class="config-value">{{ selectedChannel.id }}</span>
                </div>
                <div class="config-item">
                  <span class="config-label">名称</span>
                  <span class="config-value">{{ selectedChannel.name }}</span>
                </div>
                <template v-if="selectedChannel.protocol === 'mqtt'">
                  <div class="config-item">
                    <span class="config-label">Broker</span>
                    <span class="config-value">{{ selectedChannel.connection.broker }}:{{ selectedChannel.connection.port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">客户端ID</span>
                    <span class="config-value code">{{ selectedChannel.connection.client_id }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">主题</span>
                    <span class="config-value code">{{ selectedChannel.connection.topic }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">QoS</span>
                    <span class="config-value">{{ selectedChannel.connection.qos }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">保活</span>
                    <span class="config-value">{{ selectedChannel.connection.keepalive }}秒</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">适配器</span>
                    <span class="config-value">
                      <el-tag v-if="selectedChannel.adapter.adapter" size="small" type="primary">{{ selectedChannel.adapter.adapter }}</el-tag>
                      <span v-else class="muted">标准</span>
                    </span>
                  </div>
                  <div v-if="selectedChannel.connection.username" class="config-item">
                    <span class="config-label">用户名</span>
                    <span class="config-value">{{ selectedChannel.connection.username }}</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'xnc'">
                  <div class="config-item">
                    <span class="config-label">本地端口</span>
                    <span class="config-value">{{ selectedChannel.connection.local_port }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">远程主机</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_host || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">远程端口</span>
                    <span class="config-value">{{ selectedChannel.connection.remote_port || '--' }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">重连间隔</span>
                    <span class="config-value">{{ selectedChannel.connection.reconnect_interval || 5 }}秒</span>
                  </div>
                </template>
                <template v-if="selectedChannel.protocol === 'http'">
                  <div class="config-item full-width">
                    <span class="config-label">端点</span>
                    <span class="config-value code">{{ selectedChannel.connection.endpoint }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">方法</span>
                    <span class="config-value">{{ selectedChannel.connection.method }}</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">超时</span>
                    <span class="config-value">{{ selectedChannel.connection.timeout }}秒</span>
                  </div>
                </template>
              </div>
              <!-- 适配器配置JSON -->
              <div v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.adapter.config && Object.keys(selectedChannel.adapter.config).length > 0" class="adapter-config">
                <div class="adapter-config-title">适配器配置</div>
                <pre class="json-config">{{ JSON.stringify(selectedChannel.adapter.config, null, 2) }}</pre>
              </div>
            </div>

            <!-- 上传策略（可折叠） -->
            <el-collapse class="detail-collapse">
              <el-collapse-item title="上传策略">
                <div class="config-grid">
                  <div class="config-item">
                    <span class="config-label">立即上传</span>
                    <span class="config-value">
                      <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'" size="small">
                        {{ selectedChannel.upload_strategy.immediate_upload ? '是' : '否' }}
                      </el-tag>
                    </span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">批量大小</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.batch_size }} 条</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">上传间隔</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.interval }} 秒</span>
                  </div>
                  <div class="config-item">
                    <span class="config-label">重试次数</span>
                    <span class="config-value">{{ selectedChannel.upload_strategy.retry_times }} 次</span>
                  </div>
                </div>
              </el-collapse-item>
              <el-collapse-item v-if="selectedChannel.description" title="描述">
                <p class="description-text">{{ selectedChannel.description }}</p>
              </el-collapse-item>
            </el-collapse>
          </div>
        </template>
      </div>
    </div>
    
    <el-dialog
      v-model="showChannelDialog"
      :title="isEditing ? '编辑通道' : '新增通道'"
      width="min(900px, 90vw)"
      :close-on-click-modal="false"
    >
      <el-form ref="channelFormRef" :model="channelForm" :rules="channelFormRules" label-width="100px">

        <!-- 卡片1: 基本信息 -->
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">基本信息</span>
              <el-tag type="danger" size="small">必填</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="通道ID" prop="id">
                <el-input
                  v-model="channelForm.id"
                  placeholder="仅允许字母、数字、下划线、连字符"
                  :disabled="isEditing"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="通道名称" prop="name">
                <el-input v-model="channelForm.name" placeholder="请输入通道名称" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="协议类型" prop="protocol">
                <el-select v-model="channelForm.protocol" placeholder="请选择协议" @change="handleProtocolChange">
                  <el-option
                    v-for="opt in protocolOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="启用">
                <el-switch v-model="channelForm.enabled" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="描述">
            <el-input v-model="channelForm.description" type="textarea" :rows="2" placeholder="请输入通道描述" />
          </el-form-item>
        </el-card>

        <!-- 卡片2: 连接配置 -->
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">连接配置</span>
              <el-tag type="danger" size="small">必填</el-tag>
            </div>
          </template>

          <!-- MQTT/HTTP 连接配置 -->
          <template v-if="channelForm.protocol !== 'xnc'">
            <el-row :gutter="20">
              <el-col :span="16">
                <el-form-item label="主机地址" prop="host">
                  <el-input v-model="channelForm.host" placeholder="请输入主机地址，如 mqtt.example.com" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="端口">
                  <el-input-number v-model="channelForm.port" :min="1" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="用户名">
                  <el-input v-model="channelForm.username" placeholder="可选" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="密码">
                  <el-input v-model="channelForm.password" type="password" placeholder="可选" show-password />
                </el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- XNC 连接配置 -->
          <template v-if="channelForm.protocol === 'xnc'">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="本地端口">
                  <el-input-number v-model="channelForm.local_port" :min="1024" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="远程主机">
                  <el-input v-model="channelForm.remote_host" placeholder="XNC服务器地址" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="远程端口">
                  <el-input-number v-model="channelForm.remote_port" :min="1" :max="65535" class="full-width" />
                </el-form-item>
              </el-col>
            </el-row>
          </template>
        </el-card>

        <!-- 卡片3: MQTT适配器配置 -->
        <el-card v-if="channelForm.protocol === 'mqtt'" class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">适配器配置</span>
              <el-tag v-if="channelForm.adapter === 'C001'" type="danger" size="small">必填</el-tag>
              <el-tag v-else type="info" size="small">可选</el-tag>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="适配器">
                <el-select v-model="channelForm.adapter" placeholder="选择适配器或客户编号" filterable allow-create @change="handleAdapterChange">
                  <el-option
                    v-for="opt in mqttAdapterOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  >
                    <span>{{ opt.label }}</span>
                    <span class="option-desc">{{ opt.description }}</span>
                  </el-option>
                </el-select>
                <div class="form-hint">
                  可选择预置适配器，也可直接输入客户编号
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12" v-if="channelForm.adapter === 'C001'">
              <el-form-item label="产品Key" required>
                <el-input
                  v-model="productKey"
                  placeholder="请输入产品Key，如: al12345"
                />
                <div class="form-hint">
                  客户A平台的产品标识
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <!-- 客户A模板配置 -->
          <el-form-item v-if="channelForm.adapter === 'C001'" label=" ">
            <el-collapse class="full-width">
              <el-collapse-item title="模板配置（通常无需修改）">
                <el-alert type="info" :closable="false" class="alert-with-margin">
                  Topic模板已使用客户A协议默认值，通常无需修改
                </el-alert>
                <el-input
                  v-model="channelForm.adapter_config"
                  type="textarea"
                  :rows="15"
                  placeholder="JSON格式配置"
                />
              </el-collapse-item>
            </el-collapse>
          </el-form-item>

          <!-- 其他适配器JSON配置 -->
          <el-form-item v-else-if="channelForm.adapter !== 'standard'" label="适配器配置">
            <el-input
              v-model="channelForm.adapter_config"
              type="textarea"
              :rows="5"
              placeholder='JSON格式，如 {"productKey": "al12345", "topic_templates": {...}}'
            />
            <div class="form-hint">
              适配器专属配置，不同适配器支持不同参数
            </div>
          </el-form-item>
        </el-card>

        <!-- 卡片4: 高级配置（默认折叠） -->
        <el-card class="config-card optional" shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">高级配置</span>
              <el-tag type="info" size="small">可选</el-tag>
            </div>
          </template>
          <el-collapse>
            <!-- MQTT高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'mqtt'" title="MQTT参数">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="客户端ID">
                    <el-input v-model="channelForm.client_id" placeholder="客户端标识符" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="QoS">
                    <el-radio-group v-model="channelForm.qos">
                      <el-radio :value="0">0 - 最多一次</el-radio>
                      <el-radio :value="1">1 - 至少一次</el-radio>
                      <el-radio :value="2">2 - 恰好一次</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="保活时间">
                    <el-input-number v-model="channelForm.keepalive" :min="10" :max="3600" />
                    <span class="unit-hint">秒</span>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="清除会话">
                    <el-switch v-model="channelForm.clean_session" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="发布模式">
                    <el-radio-group v-model="channelForm.publish_mode">
                      <el-radio value="single">单条发送</el-radio>
                      <el-radio value="batch">批量发送</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="命令超时">
                    <el-input-number v-model="channelForm.command_timeout" :min="5" :max="300" />
                    <span class="unit-hint">秒</span>
                  </el-form-item>
                </el-col>
              </el-row>
              <!-- 客户A适配器不需要设置主题和命令主题 -->
              <template v-if="channelForm.adapter !== 'C001'">
                <el-row :gutter="20">
                  <el-col :span="12">
                    <el-form-item label="主题">
                      <el-input v-model="channelForm.topic" placeholder="数据上传主题，如 data/upload" />
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="命令主题">
                      <el-input v-model="channelForm.command_topic" placeholder="命令订阅主题，如 xagent/command" />
                    </el-form-item>
                  </el-col>
                </el-row>
              </template>
            </el-collapse-item>

            <!-- XNC高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'xnc'" title="XNC参数">
              <el-form-item label="重连间隔">
                <el-input-number v-model="channelForm.reconnect_interval" :min="1" :max="300" />
                <span class="unit-hint">秒（与服务器断开后重连）</span>
              </el-form-item>
              <el-form-item label="映射配置">
                <el-input
                  v-model="channelForm.mapping_config"
                  type="textarea"
                  :rows="6"
                  placeholder='点击下方"填充模板"按钮'
                />
                <div class="mapping-help">
                  <div class="mapping-help-text">
                    用于Protobuf格式的设备ID和点位映射。留空则自动分配。
                  </div>
                  <el-button type="primary" link size="small" @click="fillMappingTemplate">
                    填充模板
                  </el-button>
                </div>
              </el-form-item>
            </el-collapse-item>

            <!-- HTTP高级参数 -->
            <el-collapse-item v-if="channelForm.protocol === 'http'" title="HTTP参数">
              <el-form-item label="端点URL">
                <el-input v-model="channelForm.endpoint" placeholder="如 https://api.example.com/data" />
              </el-form-item>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="请求方法">
                    <el-radio-group v-model="channelForm.method">
                      <el-radio value="GET">GET</el-radio>
                      <el-radio value="POST">POST</el-radio>
                      <el-radio value="PUT">PUT</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="超时时间">
                    <el-input-number v-model="channelForm.timeout" :min="1" :max="300" />
                    <span class="unit-hint">秒</span>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="请求头">
                <el-input
                  v-model="channelForm.headers"
                  type="textarea"
                  :rows="3"
                  placeholder='JSON格式，如 {"Content-Type": "application/json"}'
                />
              </el-form-item>
            </el-collapse-item>

            <!-- 上传策略 -->
            <el-collapse-item title="上传策略">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="立即上传">
                    <el-switch v-model="channelForm.immediate_upload" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="批量大小">
                    <el-input-number v-model="channelForm.batch_size" :min="1" :max="10000" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="上传间隔">
                    <el-input-number v-model="channelForm.interval" :min="1" :max="3600" />
                    <span class="unit-hint">秒</span>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="重试次数">
                    <el-input-number v-model="channelForm.retry_times" :min="0" :max="10" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="重试间隔">
                <el-input-number v-model="channelForm.retry_interval" :min="1" :max="300" />
                <span class="unit-hint">秒（数据发送失败后重试）</span>
              </el-form-item>
            </el-collapse-item>

            <!-- 其他配置 -->
            <el-collapse-item title="其他配置">
              <el-form-item label="标签">
                <el-input v-model="channelForm.tags" placeholder="多个标签用逗号分隔，如: 生产环境,重要" />
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </el-card>

      </el-form>
      <template #footer>
        <el-button @click="showChannelDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveChannel" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

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
.channels-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 配置卡片样式 */
.config-card {
  margin-bottom: 16px;
  border: 1px solid #e4e7ed;
}

.config-card.optional {
  border-color: #e4e7ed;
  background: #fafafa;
}

.config-card :deep(.el-card__header) {
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.config-card :deep(.el-card__body) {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
  color: #2c3e50;
}

/* 折叠面板样式 */
.config-card :deep(.el-collapse) {
  border: none;
}

.config-card :deep(.el-collapse-item__header) {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 0 12px;
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.config-card :deep(.el-collapse-item__wrap) {
  border: 1px solid #e4e7ed;
  border-top: none;
  border-radius: 0 0 4px 4px;
}

.config-card :deep(.el-collapse-item__content) {
  padding: 16px;
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

.channel-grid {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  align-content: start;
}

.channel-card-compact {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.channel-card-compact:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.channel-card-compact.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.channel-card-compact.offline {
  opacity: 0.7;
}

.channel-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.channel-card-status {
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

.channel-card-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.channel-card-info {
  flex: 1;
  min-width: 0;
}

.channel-card-name {
  font-size: 15px;
  font-weight: 600;
  color: #2c3e50;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.channel-card-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-mini {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-mini-label {
  font-size: 11px;
  color: #909399;
}

.stat-mini-value {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}

.channel-card-actions {
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

.channel-list-panel {
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

.channel-count {
  font-size: 13px;
  color: #909399;
}

.channel-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.channel-item {
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

.channel-item:hover {
  background: #f5f7fa;
}

.channel-item.selected {
  background: #ecf5ff;
  border-color: #409eff;
}

.channel-item.offline {
  opacity: 0.7;
}

.channel-item-status {
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

.channel-item-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.channel-item-content {
  flex: 1;
  min-width: 0;
}

.channel-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.channel-item-name {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-item-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
}

.channel-item-actions {
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

.details-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.empty-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
}

.empty-details p {
  margin-top: 16px;
  font-size: 14px;
}

.details-actions {
  display: flex;
  gap: 8px;
}

.channel-details-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 标题栏状态信息 */
.header-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 12px;
}

.header-info .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f56c6c;
  flex-shrink: 0;
}

.header-info .status-dot.online {
  background: #67c23a;
}

.protocol-tag {
  padding: 2px 8px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

/* 统计区域 - 简约风格 */
.stats-dashboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.upload-icon {
  background: #ecf5ff;
  color: #409eff;
}

.success-icon {
  background: #f0f9eb;
  color: #67c23a;
}

.backlog-icon {
  background: #fdf6ec;
  color: #e6a23c;
}

.total-icon {
  background: #f4f4f5;
  color: #909399;
}

.stat-content {
  flex: 1;
}

.stat-content .stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #2c3e50;
  line-height: 1.2;
}

.stat-content .stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

/* 连接配置区域 */
.config-section {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.section-title {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #2c3e50;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  background: #f0f0f0;
}

.config-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  min-height: 40px;
}

.config-item.full-width {
  grid-column: span 2;
}

.config-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 13px;
  color: #909399;
}

.config-value {
  flex: 1;
  font-size: 13px;
  color: #2c3e50;
  word-break: break-all;
}

.config-value.code {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
}

.config-value .muted {
  color: #909399;
}

/* 适配器配置 */
.adapter-config {
  border-top: 1px solid #e4e7ed;
  padding: 12px 16px;
}

.adapter-config-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.json-config {
  margin: 0;
  padding: 12px;
  background: #f5f7fa;
  color: #2c3e50;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  border: 1px solid #e4e7ed;
}

/* 折叠面板 */
.detail-collapse {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.detail-collapse :deep(.el-collapse-item__header) {
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 16px;
  height: 42px;
  line-height: 42px;
  font-size: 14px;
  font-weight: 500;
  color: #2c3e50;
}

.detail-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.detail-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.description-text {
  margin: 0;
  padding: 16px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

/* 映射配置帮助 */
.mapping-help {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.mapping-help-text {
  font-size: 12px;
  color: #909399;
}

.detail-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: #2c3e50;
}

.statistics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.stat-box {
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-box-value {
  font-size: 24px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 4px;
}

.stat-box-label {
  font-size: 12px;
  color: #909399;
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

  .channel-list-panel {
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

  .channel-list-panel {
    width: 100%;
    min-width: 0;
    max-height: 280px;
  }

  .details-panel {
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

  /* 详情页响应式 */
  .stats-dashboard {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-content .stat-value {
    font-size: 18px;
  }

  .config-grid {
    grid-template-columns: 1fr;
  }

  .config-item.full-width {
    grid-column: span 1;
  }

  .header-info {
    display: none;
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

  .channel-list-panel {
    max-height: 220px;
  }

  .channel-item {
    padding: 10px;
  }

  .channel-item-meta {
    flex-direction: column;
    gap: 2px;
  }
}

@media (pointer: coarse) {
  .channel-item {
    padding: 14px 12px;
    min-height: 56px;
  }

  .channel-item-actions {
    gap: 8px;
  }

  .more-btn {
    padding: 8px;
    min-width: 36px;
    min-height: 36px;
  }

  .channel-item-status {
    width: 36px;
    height: 36px;
  }

  .el-button {
    min-height: 36px;
  }
}

@media (max-width: 1024px) {
  .channel-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 8px;
    padding: 8px;
  }

  .channel-card-compact {
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

  .channel-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px;
    padding: 6px;
  }

  .channel-card-compact {
    padding: 10px;
  }

  .channel-card-header {
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

/* 表单辅助样式 */
.full-width {
  width: 100%;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.unit-hint {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.option-desc {
  float: right;
  color: #8492a6;
  font-size: 12px;
}

.danger-text {
  color: #f56c6c;
}

.alert-with-margin {
  margin-bottom: 12px;
}
</style>
