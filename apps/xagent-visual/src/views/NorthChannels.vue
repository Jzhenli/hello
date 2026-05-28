<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
  RefreshRight,
  VideoPlay,
  Document
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

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
  local_port: 8888,
  xnc_protocol: 'protobuf' as 'protobuf' | 'json',
  remote_host: '127.0.0.1',
  remote_port: 9000,
  reconnect_interval: 5,
  mapping_config: '{}',
  endpoint: '',
  method: 'POST' as 'GET' | 'POST' | 'PUT',
  headers: '{}',
  timeout: 30,
  adapter: 'xnc_protobuf',
  adapter_config: '{}',
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
      clean_session: true
    }
  },
  { 
    label: 'XNC', 
    value: 'xnc', 
    defaultPort: 9000,
    defaultConfig: { 
      local_port: 8888,
      xnc_protocol: 'protobuf',
      remote_host: '127.0.0.1',
      remote_port: 9000,
      reconnect_interval: 5,
      adapter: 'xnc_protobuf'
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
    local_port: 8888,
    xnc_protocol: 'protobuf',
    remote_host: '127.0.0.1',
    remote_port: 9000,
    reconnect_interval: 5,
    mapping_config: '{}',
    endpoint: '',
    method: 'POST',
    headers: '{}',
    timeout: 30,
    adapter: 'xnc_protobuf',
    adapter_config: '{}',
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
    host: channel.protocol === 'xnc' 
      ? (fullChannel.connection.xnc?.remote_host || '127.0.0.1')
      : channel.host,
    port: channel.protocol === 'xnc' 
      ? (fullChannel.connection.xnc?.remote_port || 9000)
      : channel.port,
    username: channel.protocol === 'xnc' ? '' : (fullChannel.connection.username || ''),
    password: '',
    client_id: fullChannel.connection.mqtt?.client_id || '',
    topic: fullChannel.connection.mqtt?.topic || '',
    qos: fullChannel.connection.mqtt?.qos || 0,
    keepalive: fullChannel.connection.mqtt?.keepalive || 60,
    clean_session: fullChannel.connection.mqtt?.clean_session ?? true,
    local_port: fullChannel.connection.xnc?.local_port || 8888,
    xnc_protocol: fullChannel.connection.xnc?.protocol || 'protobuf',
    remote_host: fullChannel.connection.xnc?.remote_host || '127.0.0.1',
    remote_port: fullChannel.connection.xnc?.remote_port || 9000,
    reconnect_interval: fullChannel.connection.xnc?.reconnect_interval || 5,
    mapping_config: JSON.stringify(fullChannel.connection.xnc?.mapping_config || {}, null, 2),
    endpoint: fullChannel.connection.http?.endpoint || '',
    method: fullChannel.connection.http?.method || 'POST',
    headers: JSON.stringify(fullChannel.connection.http?.headers || {}, null, 2),
    timeout: fullChannel.connection.http?.timeout || 30,
    adapter: fullChannel.adapter.type,
    adapter_config: JSON.stringify(fullChannel.adapter.config, null, 2),
    immediate_upload: fullChannel.upload_strategy.immediate_upload,
    batch_size: fullChannel.upload_strategy.batch_size,
    interval: fullChannel.upload_strategy.interval,
    retry_times: fullChannel.upload_strategy.retry_times,
    retry_interval: fullChannel.upload_strategy.retry_interval || 5,
    tags: (fullChannel.tags || []).join(', ')
  }
  showChannelDialog.value = true
}

const buildChannelConfig = (): NorthChannelConfig => {
  const connection: any = {
    host: channelForm.value.protocol === 'xnc' 
      ? channelForm.value.remote_host 
      : channelForm.value.host,
    port: channelForm.value.protocol === 'xnc' 
      ? channelForm.value.remote_port 
      : channelForm.value.port
  }
  
  if (channelForm.value.protocol === 'mqtt') {
    if (channelForm.value.username) {
      connection.username = channelForm.value.username
    }
    if (channelForm.value.password) {
      connection.password = channelForm.value.password
    }
    connection.mqtt = {
      client_id: channelForm.value.client_id,
      topic: channelForm.value.topic,
      qos: channelForm.value.qos,
      keepalive: channelForm.value.keepalive,
      clean_session: channelForm.value.clean_session
    }
  } else if (channelForm.value.protocol === 'xnc') {
    connection.xnc = {
      local_port: channelForm.value.local_port,
      protocol: channelForm.value.xnc_protocol,
      remote_host: channelForm.value.remote_host,
      remote_port: channelForm.value.remote_port,
      reconnect_interval: channelForm.value.reconnect_interval
    }
    
    try {
      const mappingConfig = JSON.parse(channelForm.value.mapping_config)
      if (Object.keys(mappingConfig).length > 0) {
        connection.xnc.mapping_config = mappingConfig
      }
    } catch (e) {
      console.error('Invalid mapping config JSON:', e)
    }
  } else if (channelForm.value.protocol === 'http') {
    if (channelForm.value.username) {
      connection.username = channelForm.value.username
    }
    if (channelForm.value.password) {
      connection.password = channelForm.value.password
    }
    connection.http = {
      endpoint: channelForm.value.endpoint,
      method: channelForm.value.method,
      timeout: channelForm.value.timeout
    }
    try {
      const headers = JSON.parse(channelForm.value.headers)
      if (Object.keys(headers).length > 0) {
        connection.http.headers = headers
      }
    } catch (e) {
      console.error('Invalid headers JSON:', e)
    }
  }
  
  let adapterConfig = {}
  try {
    adapterConfig = JSON.parse(channelForm.value.adapter_config)
  } catch (e) {
    console.error('Invalid adapter config JSON:', e)
  }
  
  const config: any = {
    id: channelForm.value.id,
    name: channelForm.value.name,
    enabled: channelForm.value.enabled,
    protocol: channelForm.value.protocol,
    connection,
    adapter: {
      type: channelForm.value.adapter,
      config: adapterConfig
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
            <div class="panel-header-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" @click="handleTestConnection(selectedChannelId!)">
                测试连接
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" @click="handleRestartChannel(selectedChannelId!)">
                重启
              </el-button>
            </div>
          </div>
          
          <div v-if="selectedChannel" class="channel-details-content">
            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>基本信息</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="通道ID">{{ selectedChannel.id }}</el-descriptions-item>
                <el-descriptions-item label="名称">{{ selectedChannel.name }}</el-descriptions-item>
                <el-descriptions-item label="协议">{{ selectedChannel.protocol.toUpperCase() }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="selectedChannel.status === 'online' ? 'success' : 'danger'">
                    {{ selectedChannel.status === 'online' ? '在线' : '离线' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="启用">
                  <el-tag :type="selectedChannel.enabled ? 'success' : 'info'">
                    {{ selectedChannel.enabled ? '是' : '否' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">
                  {{ selectedChannel.description || '--' }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>连接配置</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="主机">{{ selectedChannel.connection.host }}</el-descriptions-item>
                <el-descriptions-item label="端口">{{ selectedChannel.connection.port }}</el-descriptions-item>
                <el-descriptions-item label="用户名">{{ selectedChannel.connection.username || '--' }}</el-descriptions-item>
                <el-descriptions-item label="密码">{{ selectedChannel.connection.password ? '***' : '--' }}</el-descriptions-item>
                
                <template v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.connection.mqtt">
                  <el-descriptions-item label="客户端ID">{{ selectedChannel.connection.mqtt.client_id }}</el-descriptions-item>
                  <el-descriptions-item label="主题">{{ selectedChannel.connection.mqtt.topic }}</el-descriptions-item>
                  <el-descriptions-item label="QoS">{{ selectedChannel.connection.mqtt.qos }}</el-descriptions-item>
                  <el-descriptions-item label="保活">{{ selectedChannel.connection.mqtt.keepalive }}秒</el-descriptions-item>
                </template>
                
                <template v-if="selectedChannel.protocol === 'xnc' && selectedChannel.connection.xnc">
                  <el-descriptions-item label="本地端口">{{ selectedChannel.connection.xnc.local_port }}</el-descriptions-item>
                  <el-descriptions-item label="协议模式">{{ selectedChannel.connection.xnc.protocol || 'protobuf' }}</el-descriptions-item>
                  <el-descriptions-item label="远程主机">{{ selectedChannel.connection.xnc.remote_host || '--' }}</el-descriptions-item>
                  <el-descriptions-item label="远程端口">{{ selectedChannel.connection.xnc.remote_port || '--' }}</el-descriptions-item>
                  <el-descriptions-item label="重连间隔">{{ selectedChannel.connection.xnc.reconnect_interval || 5 }}秒</el-descriptions-item>
                </template>
                
                <template v-if="selectedChannel.protocol === 'http' && selectedChannel.connection.http">
                  <el-descriptions-item label="端点" :span="2">{{ selectedChannel.connection.http.endpoint }}</el-descriptions-item>
                  <el-descriptions-item label="方法">{{ selectedChannel.connection.http.method }}</el-descriptions-item>
                  <el-descriptions-item label="超时">{{ selectedChannel.connection.http.timeout }}秒</el-descriptions-item>
                </template>
              </el-descriptions>
            </el-card>

            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>上传策略</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="立即上传">
                  <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'">
                    {{ selectedChannel.upload_strategy.immediate_upload ? '是' : '否' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="批量大小">{{ selectedChannel.upload_strategy.batch_size }}</el-descriptions-item>
                <el-descriptions-item label="上传间隔">{{ selectedChannel.upload_strategy.interval }}秒</el-descriptions-item>
                <el-descriptions-item label="重试次数">{{ selectedChannel.upload_strategy.retry_times }}</el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card v-if="selectedChannel.statistics" class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>实时统计</span>
                </div>
              </template>
              <div class="statistics-grid">
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-box-label">上传速率(条/分)</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-box-label">成功率</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-box-label">积压数量</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.total_uploaded }}</div>
                  <div class="stat-box-label">总上传数</div>
                </div>
              </div>
            </el-card>
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
                      <span style="color: #f56c6c">删除</span>
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
            <span class="panel-title">{{ selectedChannel?.name }} 详情</span>
            <div class="details-actions">
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="primary" size="small" @click="handleTestConnection(selectedChannelId!)">
                测试连接
              </el-button>
              <el-button v-if="userStore.hasPermission('devices', 'update')" type="warning" size="small" @click="handleRestartChannel(selectedChannelId!)">
                重启
              </el-button>
            </div>
          </div>
          
          <div v-if="selectedChannel" class="channel-details-content">
            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>基本信息</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="通道ID">{{ selectedChannel.id }}</el-descriptions-item>
                <el-descriptions-item label="名称">{{ selectedChannel.name }}</el-descriptions-item>
                <el-descriptions-item label="协议">{{ selectedChannel.protocol.toUpperCase() }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="selectedChannel.status === 'online' ? 'success' : 'danger'">
                    {{ selectedChannel.status === 'online' ? '在线' : '离线' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="启用">
                  <el-tag :type="selectedChannel.enabled ? 'success' : 'info'">
                    {{ selectedChannel.enabled ? '是' : '否' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="描述" :span="2">
                  {{ selectedChannel.description || '--' }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>连接配置</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="主机">{{ selectedChannel.connection.host }}</el-descriptions-item>
                <el-descriptions-item label="端口">{{ selectedChannel.connection.port }}</el-descriptions-item>
                <el-descriptions-item label="用户名">{{ selectedChannel.connection.username || '--' }}</el-descriptions-item>
                <el-descriptions-item label="密码">{{ selectedChannel.connection.password ? '***' : '--' }}</el-descriptions-item>
                
                <template v-if="selectedChannel.protocol === 'mqtt' && selectedChannel.connection.mqtt">
                  <el-descriptions-item label="客户端ID">{{ selectedChannel.connection.mqtt.client_id }}</el-descriptions-item>
                  <el-descriptions-item label="主题">{{ selectedChannel.connection.mqtt.topic }}</el-descriptions-item>
                  <el-descriptions-item label="QoS">{{ selectedChannel.connection.mqtt.qos }}</el-descriptions-item>
                  <el-descriptions-item label="保活">{{ selectedChannel.connection.mqtt.keepalive }}秒</el-descriptions-item>
                </template>
                
                <template v-if="selectedChannel.protocol === 'xnc' && selectedChannel.connection.xnc">
                  <el-descriptions-item label="本地端口">{{ selectedChannel.connection.xnc.local_port }}</el-descriptions-item>
                  <el-descriptions-item label="协议模式">{{ selectedChannel.connection.xnc.protocol || 'protobuf' }}</el-descriptions-item>
                  <el-descriptions-item label="远程主机">{{ selectedChannel.connection.xnc.remote_host || '--' }}</el-descriptions-item>
                  <el-descriptions-item label="远程端口">{{ selectedChannel.connection.xnc.remote_port || '--' }}</el-descriptions-item>
                  <el-descriptions-item label="重连间隔">{{ selectedChannel.connection.xnc.reconnect_interval || 5 }}秒</el-descriptions-item>
                </template>
                
                <template v-if="selectedChannel.protocol === 'http' && selectedChannel.connection.http">
                  <el-descriptions-item label="端点" :span="2">{{ selectedChannel.connection.http.endpoint }}</el-descriptions-item>
                  <el-descriptions-item label="方法">{{ selectedChannel.connection.http.method }}</el-descriptions-item>
                  <el-descriptions-item label="超时">{{ selectedChannel.connection.http.timeout }}秒</el-descriptions-item>
                </template>
              </el-descriptions>
            </el-card>

            <el-card class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>上传策略</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="立即上传">
                  <el-tag :type="selectedChannel.upload_strategy.immediate_upload ? 'success' : 'info'">
                    {{ selectedChannel.upload_strategy.immediate_upload ? '是' : '否' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="批量大小">{{ selectedChannel.upload_strategy.batch_size }}</el-descriptions-item>
                <el-descriptions-item label="上传间隔">{{ selectedChannel.upload_strategy.interval }}秒</el-descriptions-item>
                <el-descriptions-item label="重试次数">{{ selectedChannel.upload_strategy.retry_times }}</el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card v-if="selectedChannel.statistics" class="detail-card">
              <template #header>
                <div class="card-header">
                  <span>实时统计</span>
                </div>
              </template>
              <div class="statistics-grid">
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.upload_rate }}</div>
                  <div class="stat-box-label">上传速率(条/分)</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.success_rate }}%</div>
                  <div class="stat-box-label">成功率</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.backlog_count }}</div>
                  <div class="stat-box-label">积压数量</div>
                </div>
                <div class="stat-box">
                  <div class="stat-box-value">{{ selectedChannel.statistics.total_uploaded }}</div>
                  <div class="stat-box-label">总上传数</div>
                </div>
              </div>
            </el-card>
          </div>
        </template>
      </div>
    </div>
    
    <el-dialog 
      v-model="showChannelDialog" 
      :title="isEditing ? '编辑通道' : '新增通道'"
      width="min(800px, 90vw)"
      :close-on-click-modal="false"
    >
      <el-form ref="channelFormRef" :model="channelForm" :rules="channelFormRules" label-width="120px">
        <el-form-item label="通道ID" prop="id">
          <el-input 
            v-model="channelForm.id" 
            placeholder="仅允许字母、数字、下划线、连字符"
            :disabled="isEditing"
          />
        </el-form-item>
        <el-form-item label="通道名称" prop="name">
          <el-input v-model="channelForm.name" placeholder="请输入通道名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="channelForm.description" type="textarea" :rows="2" placeholder="请输入通道描述" />
        </el-form-item>
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
        
        <template v-if="channelForm.protocol !== 'xnc'">
          <el-divider content-position="left">连接配置</el-divider>
          
          <el-form-item label="主机地址" prop="host">
            <el-input v-model="channelForm.host" placeholder="请输入主机地址，如 mqtt.example.com" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="channelForm.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="channelForm.username" placeholder="可选" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="channelForm.password" type="password" placeholder="可选" show-password />
          </el-form-item>
        </template>
        
        <template v-if="channelForm.protocol === 'mqtt'">
          <el-divider content-position="left">MQTT 配置</el-divider>
          
          <el-form-item label="客户端ID">
            <el-input v-model="channelForm.client_id" placeholder="客户端标识符" />
          </el-form-item>
          <el-form-item label="主题">
            <el-input v-model="channelForm.topic" placeholder="数据上传主题，如 data/upload" />
          </el-form-item>
          <el-form-item label="QoS">
            <el-radio-group v-model="channelForm.qos">
              <el-radio :value="0">0 - 最多一次</el-radio>
              <el-radio :value="1">1 - 至少一次</el-radio>
              <el-radio :value="2">2 - 恰好一次</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="保活时间">
            <el-input-number v-model="channelForm.keepalive" :min="10" :max="3600" />
            <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
          </el-form-item>
          <el-form-item label="清除会话">
            <el-switch v-model="channelForm.clean_session" />
          </el-form-item>
        </template>
        
        <template v-if="channelForm.protocol === 'xnc'">
          <el-divider content-position="left">XNC 配置</el-divider>
          
          <el-form-item label="本地端口">
            <el-input-number v-model="channelForm.local_port" :min="1024" :max="65535" />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              UDP监听端口，用于接收下行命令
            </div>
          </el-form-item>
          <el-form-item label="协议模式">
            <el-radio-group v-model="channelForm.xnc_protocol">
              <el-radio value="protobuf">Protobuf</el-radio>
              <el-radio value="json">JSON</el-radio>
            </el-radio-group>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              Protobuf格式更高效，JSON格式更易调试
            </div>
          </el-form-item>
          <el-form-item label="远程主机">
            <el-input v-model="channelForm.remote_host" placeholder="XNC服务器地址" />
          </el-form-item>
          <el-form-item label="远程端口">
            <el-input-number v-model="channelForm.remote_port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="重连间隔">
            <el-input-number v-model="channelForm.reconnect_interval" :min="1" :max="300" />
            <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
          </el-form-item>
          <el-form-item label="适配器">
            <el-select v-model="channelForm.adapter" placeholder="请选择适配器">
              <el-option label="Protobuf适配器" value="xnc_protobuf" />
              <el-option label="JSON适配器" value="xnc_json" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="channelForm.adapter === 'xnc_protobuf'" label="映射配置">
            <el-input 
              v-model="channelForm.mapping_config" 
              type="textarea" 
              :rows="4" 
              placeholder='JSON格式的设备映射配置'
            />
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              用于Protobuf格式的设备ID和点位映射
            </div>
          </el-form-item>
        </template>
        
        <template v-if="channelForm.protocol === 'http'">
          <el-divider content-position="left">HTTP 配置</el-divider>
          
          <el-form-item label="端点URL">
            <el-input v-model="channelForm.endpoint" placeholder="如 https://api.example.com/data" />
          </el-form-item>
          <el-form-item label="请求方法">
            <el-radio-group v-model="channelForm.method">
              <el-radio value="GET">GET</el-radio>
              <el-radio value="POST">POST</el-radio>
              <el-radio value="PUT">PUT</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="请求头">
            <el-input 
              v-model="channelForm.headers" 
              type="textarea" 
              :rows="3" 
              placeholder='JSON格式，如 {"Content-Type": "application/json"}'
            />
          </el-form-item>
          <el-form-item label="超时时间">
            <el-input-number v-model="channelForm.timeout" :min="1" :max="300" />
            <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
          </el-form-item>
        </template>
        
        <el-divider content-position="left">上传策略</el-divider>
        
        <el-form-item label="立即上传">
          <el-switch v-model="channelForm.immediate_upload" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            开启后数据会立即上传，关闭则按间隔批量上传
          </div>
        </el-form-item>
        <el-form-item label="批量大小">
          <el-input-number v-model="channelForm.batch_size" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="上传间隔">
          <el-input-number v-model="channelForm.interval" :min="1" :max="3600" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
        </el-form-item>
        <el-form-item label="重试次数">
          <el-input-number v-model="channelForm.retry_times" :min="0" :max="10" />
        </el-form-item>
        <el-form-item label="重试间隔">
          <el-input-number v-model="channelForm.retry_interval" :min="1" :max="300" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px;">秒</span>
        </el-form-item>
        
        <el-divider content-position="left">其他配置</el-divider>
        
        <el-form-item label="适配器类型">
          <el-input v-model="channelForm.adapter_type" placeholder="默认为 default" />
        </el-form-item>
        <el-form-item label="适配器配置">
          <el-input 
            v-model="channelForm.adapter_config" 
            type="textarea" 
            :rows="3" 
            placeholder='JSON格式的适配器配置'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="channelForm.enabled" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="channelForm.tags" placeholder="多个标签用逗号分隔，如: 生产环境,重要" />
        </el-form-item>
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
</style>
