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
const activeTab = ref('south')
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
  await pointStore.fetchAllLatestReadings()
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
  tags: ''
})
const deviceFormRef = ref()
const isEditing = ref(false)
const editingAsset = ref('')
const saving = ref(false)

const pluginOptions = [
  { label: 'Modbus TCP', value: 'modbus_tcp', defaultPort: 502 },
  { label: 'Modbus RTU', value: 'modbus_rtu', defaultPort: 0 },
  { label: 'KNX', value: 'knx', defaultPort: 3671 },
  { label: 'BACnet', value: 'bacnet', defaultPort: 47808 }
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
    const config: Record<string, unknown> = {
      host: deviceForm.value.host,
      port: deviceForm.value.port
    }

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
  await pointStore.fetchLatestReadings(asset)
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
  tags: ''
})
const pointFormRef = ref()
const isEditingPoint = ref(false)
const editingPointName = ref('')
const savingPoint = ref(false)

const pointFormRules = {
  name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  data_type: [{ required: true, message: '请输入数据类型', trigger: 'blur' }]
}

const handleAddPoint = () => {
  if (!selectedDeviceAsset.value) return
  isEditingPoint.value = false
  editingPointName.value = ''
  pointForm.value = {
    name: '',
    description: '',
    data_type: 'uint16',
    standard_data_type: 'float',
    unit: '',
    enabled: true,
    configJson: '{}',
    metadataJson: '{}',
    tags: ''
  }
  showPointDialog.value = true
}

const handleEditPoint = (point: any) => {
  isEditingPoint.value = true
  editingPointName.value = point.name
  pointForm.value = {
    name: point.name,
    description: point.description || '',
    data_type: point.data_type,
    standard_data_type: point.standard_data_type || '',
    unit: point.unit || '',
    enabled: point.enabled,
    configJson: JSON.stringify(point.config || {}, null, 2),
    metadataJson: JSON.stringify(point.metadata || {}, null, 2),
    tags: (point.tags || []).join(', ')
  }
  showPointDialog.value = true
}

const handleSavePoint = async () => {
  if (!deviceFormRef.value) return
  try {
    await pointFormRef.value.validate()
  } catch {
    return
  }

  let config: Record<string, unknown>
  let metadata: Record<string, unknown>
  try {
    config = JSON.parse(pointForm.value.configJson)
  } catch {
    ElMessage.error('协议配置JSON格式错误')
    return
  }
  try {
    metadata = JSON.parse(pointForm.value.metadataJson)
  } catch {
    ElMessage.error('元数据JSON格式错误')
    return
  }

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
  await pointStore.fetchAllLatestReadings()
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
    
    <el-tabs v-model="activeTab" class="device-tabs">
      <el-tab-pane label="南向设备" name="south">
        <div v-if="deviceStore.loading && deviceStore.southDevices.length === 0" class="loading-state">
          <el-icon class="is-loading" :size="32"><Refresh /></el-icon>
          <p>加载设备列表...</p>
        </div>

        <div v-else-if="filteredSouthDevices.length === 0" class="empty-state">
          <p>暂无设备，点击"新增设备"添加</p>
        </div>

        <div v-else class="section">
          <div class="section-header">
            <h3>南向设备 ({{ filteredSouthDevices.length }})</h3>
            <span class="section-desc">数据采集设备</span>
          </div>
          <el-row :gutter="20">
            <el-col 
              v-for="device in filteredSouthDevices" 
              :key="device.asset" 
              :span="selectedDeviceAsset ? 12 : 6"
            >
              <el-card 
                class="device-card" 
                shadow="hover" 
                :class="{ offline: !device.enabled || device.status !== 'active', selected: selectedDeviceAsset === device.asset }"
                @click="handleViewPoints(device.asset)"
              >
                <div class="device-header">
                  <div class="device-status" :class="{ online: device.enabled && device.status === 'active', offline: !device.enabled || device.status !== 'active' }">
                    <el-icon v-if="device.enabled && device.status === 'active'"><CircleCheck /></el-icon>
                    <el-icon v-else><CircleClose /></el-icon>
                  </div>
                  <div class="device-name">{{ device.name }}</div>
                  <el-tag size="small" :type="getStatusType(device.status, device.enabled)">
                    {{ getStatusLabel(device.status, device.enabled) }}
                  </el-tag>
                </div>
                <div class="device-info">
                  <div class="info-row">
                    <span class="label">资产标识:</span>
                    <span class="value">{{ device.asset }}</span>
                  </div>
                  <div class="info-row">
                    <span class="label">协议:</span>
                    <span class="value">{{ device.pluginName }}</span>
                  </div>
                  <div class="info-row">
                    <span class="label">点位:</span>
                    <span class="value">{{ device.pointCount }} 个</span>
                  </div>
                  <div class="info-row">
                    <span class="label">地址:</span>
                    <span class="value">{{ device.connection.host }}:{{ device.connection.port }}</span>
                  </div>
                </div>
                <div class="device-footer">
                  <el-switch 
                    :model-value="device.enabled" 
                    size="small"
                    @click.stop
                    @change="handleToggleDevice(device.asset)"
                  />
                  <div class="actions">
                    <el-button type="primary" link size="small" @click.stop="handleViewPoints(device.asset)">
                      点位
                    </el-button>
                    <el-button type="primary" link size="small" @click.stop="handleEditDevice(device)">
                      编辑
                    </el-button>
                    <el-button link size="small" @click.stop="handleReloadDevice(device.asset)">
                      重载
                    </el-button>
                    <el-button type="danger" link size="small" @click.stop="handleDeleteDevice(device)">
                      删除
                    </el-button>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
        
        <div v-if="selectedDeviceAsset" class="points-section">
          <div class="section-header">
            <h3>{{ deviceStore.getDeviceByAsset(selectedDeviceAsset)?.name || selectedDeviceAsset }} 点位列表</h3>
            <div class="points-actions">
              <el-button type="primary" :icon="Plus" size="small" @click="handleAddPoint">
                新增点位
              </el-button>
              <el-button link @click="selectedDeviceAsset = null">关闭</el-button>
            </div>
          </div>
          <el-table :data="getDevicePoints(selectedDeviceAsset)" stripe style="width: 100%">
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
        </div>
      </el-tab-pane>
    </el-tabs>
    
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
      width="650px"
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
        <el-form-item label="数据类型" prop="data_type">
          <el-input v-model="pointForm.data_type" placeholder="协议特定类型，如 uint16, analogInput" />
        </el-form-item>
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
        <el-form-item label="启用">
          <el-switch v-model="pointForm.enabled" />
        </el-form-item>
        <el-form-item label="协议配置">
          <el-input 
            v-model="pointForm.configJson" 
            type="textarea" 
            :rows="4" 
            placeholder='如: {"address": 100, "function": "read_holding_registers"}'
          />
        </el-form-item>
        <el-form-item label="元数据">
          <el-input 
            v-model="pointForm.metadataJson" 
            type="textarea" 
            :rows="3" 
            placeholder='如: {"alarm_high": 80, "alarm_low": 20}'
          />
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
}

.page-header {
  margin-bottom: 20px;
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
  margin-bottom: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.device-tabs {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
  color: #2c3e50;
}

.section-desc {
  font-size: 13px;
  color: #7f8c8d;
}

.points-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.device-card {
  margin-bottom: 16px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.device-card:hover {
  transform: translateY(-2px);
}

.device-card.offline {
  opacity: 0.7;
}

.device-card.selected {
  border: 2px solid #3498db;
  box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
}

.device-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.device-status {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.device-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.device-status.offline {
  background: #ffebee;
  color: #e74c3c;
}

.device-name {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.device-info {
  margin-bottom: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.info-row .label {
  color: #7f8c8d;
}

.info-row .value {
  color: #2c3e50;
  font-weight: 500;
}

.device-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.actions {
  display: flex;
  gap: 4px;
}

.points-section {
  margin-top: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
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
</style>
