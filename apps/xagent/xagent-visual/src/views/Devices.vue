<script setup lang="ts">
import { ref } from 'vue'
import { useDeviceStore } from '@/stores/devices'
import { usePointStore } from '@/stores/points'
import { 
  Plus, 
  Upload, 
  Download, 
  Refresh,
  CircleCheck,
  CircleClose,
  Search,
  TrendCharts
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PointTrend from '@/components/PointTrend.vue'

const deviceStore = useDeviceStore()
const pointStore = usePointStore()

const searchQuery = ref('')
const statusFilter = ref('')
const activeTab = ref('south')
const selectedDeviceForPoints = ref<string | null>(null)
const showTrend = ref(false)
const selectedPointForTrend = ref<{ deviceName: string; pointName: string } | null>(null)

const filteredSouthDevices = ref([...deviceStore.southDevices])
const filteredNorthChannels = ref([...deviceStore.northChannels])

const handleSearch = () => {
  const query = searchQuery.value.toLowerCase()
  filteredSouthDevices.value = deviceStore.southDevices.filter(d => 
    d.name.toLowerCase().includes(query) || 
    d.protocol.toLowerCase().includes(query)
  )
  filteredNorthChannels.value = deviceStore.northChannels.filter(c => 
    c.name.toLowerCase().includes(query) || 
    c.protocol.toLowerCase().includes(query)
  )
}

const handleFilterChange = () => {
  if (statusFilter.value === '') {
    filteredSouthDevices.value = [...deviceStore.southDevices]
  } else if (statusFilter.value === 'online') {
    filteredSouthDevices.value = deviceStore.southDevices.filter(d => d.status === 'online')
  } else {
    filteredSouthDevices.value = deviceStore.southDevices.filter(d => d.status === 'offline')
  }
}

const handleToggleDevice = (name: string) => {
  deviceStore.toggleDevice(name)
  handleSearch()
}

const handleToggleChannel = (name: string) => {
  deviceStore.toggleChannel(name)
  handleSearch()
}

const showDeviceDialog = ref(false)
const editingDeviceData = ref({
  name: '',
  assetName: '',
  protocol: '',
  connection: {
    host: '',
    port: 3671
  }
})

const isEditing = ref(false)

const handleAddDevice = () => {
  isEditing.value = false
  editingDeviceData.value = {
    name: '',
    assetName: '',
    protocol: 'KNX',
    connection: {
      host: '',
      port: 3671
    }
  }
  showDeviceDialog.value = true
}

const handleEditDevice = (device: any) => {
  isEditing.value = true
  editingDeviceData.value = {
    name: device.name,
    assetName: device.assetName,
    protocol: device.protocol,
    connection: {
      host: device.connection.host,
      port: device.connection.port
    }
  }
  showDeviceDialog.value = true
}

const handleDeleteDevice = (name: string) => {
  ElMessageBox.confirm(
    `确定要删除设备 "${name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    const index = deviceStore.southDevices.findIndex(d => d.name === name)
    if (index !== -1) {
      deviceStore.southDevices.splice(index, 1)
      handleSearch()
    }
    ElMessage.success('设备已删除')
  }).catch(() => {})
}

const handleSaveDevice = () => {
  showDeviceDialog.value = false
  ElMessage.success(isEditing.value ? '设备已更新' : '设备已添加')
}

const handleViewPoints = (deviceName: string) => {
  selectedDeviceForPoints.value = deviceName
}

const handleViewTrend = (deviceName: string, pointName: string) => {
  selectedPointForTrend.value = { deviceName, pointName }
  pointStore.selectPoint(deviceName, pointName)
  showTrend.value = true
}

const handleCloseTrend = () => {
  showTrend.value = false
  selectedPointForTrend.value = null
  pointStore.clearSelection()
}

const getDevicePoints = (deviceName: string) => {
  const device = pointStore.devices.find(d => d.name === deviceName)
  return device?.points || []
}

const getQualityColor = (quality: string) => {
  return quality === 'good' ? 'success' : quality === 'bad' ? 'danger' : 'warning'
}

const getQualityLabel = (quality: string) => {
  return quality === 'good' ? '良好' : quality === 'bad' ? '异常' : '不确定'
}
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
        <el-button :icon="Upload">导入</el-button>
        <el-button :icon="Download">导出</el-button>
        <el-button :icon="Refresh" circle @click="handleSearch" />
      </div>
    </div>
    
    <el-tabs v-model="activeTab" class="device-tabs">
      <el-tab-pane label="南向设备" name="south">
        <div class="section">
          <div class="section-header">
            <h3>南向设备 ({{ filteredSouthDevices.length }})</h3>
            <span class="section-desc">数据采集设备</span>
          </div>
          <el-row :gutter="20">
            <el-col 
              v-for="device in filteredSouthDevices" 
              :key="device.name" 
              :span="selectedDeviceForPoints ? 12 : 6"
            >
              <el-card 
                class="device-card" 
                shadow="hover" 
                :class="{ offline: device.status === 'offline', selected: selectedDeviceForPoints === device.name }"
                @click="handleViewPoints(device.name)"
              >
                <div class="device-header">
                  <div class="device-status" :class="device.status">
                    <el-icon v-if="device.status === 'online'"><CircleCheck /></el-icon>
                    <el-icon v-else><CircleClose /></el-icon>
                  </div>
                  <div class="device-name">{{ device.name }}</div>
                  <el-switch 
                    v-model="device.enabled" 
                    size="small"
                    @click.stop
                    @change="handleToggleDevice(device.name)"
                  />
                </div>
                <div class="device-info">
                  <div class="info-row">
                    <span class="label">协议:</span>
                    <span class="value">{{ device.protocol }}</span>
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
                  <span class="update-time">{{ device.lastUpdate }}</span>
                  <div class="actions">
                    <el-button type="primary" link size="small" @click.stop="handleViewPoints(device.name)">
                      点位
                    </el-button>
                    <el-button type="primary" link size="small" @click.stop="handleEditDevice(device)">
                      编辑
                    </el-button>
                    <el-button type="danger" link size="small" @click.stop="handleDeleteDevice(device.name)">
                      删除
                    </el-button>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
        
        <div v-if="selectedDeviceForPoints" class="points-section">
          <div class="section-header">
            <h3>📍 {{ selectedDeviceForPoints }} 点位列表</h3>
            <el-button link @click="selectedDeviceForPoints = null">关闭</el-button>
          </div>
          <el-table :data="getDevicePoints(selectedDeviceForPoints)" stripe style="width: 100%">
            <el-table-column prop="name" label="点位名称" width="150" />
            <el-table-column prop="description" label="描述" width="180" />
            <el-table-column label="当前值" width="120">
              <template #default="{ row }">
                <span class="current-value">
                  {{ row.currentValue }} {{ row.unit }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.type === 'analog' ? 'primary' : 'success'">
                  {{ row.type === 'analog' ? '模拟' : '数字' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="质量" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="getQualityColor(row.quality)">
                  {{ getQualityLabel(row.quality) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="lastUpdate" label="更新时间" width="100" />
            <el-table-column label="趋势" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.trend.enabled" size="small" type="success">启用</el-tag>
                <el-tag v-else size="small" type="info">禁用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button 
                  v-if="row.trend.enabled"
                  type="primary" 
                  :icon="TrendCharts" 
                  size="small"
                  @click="handleViewTrend(selectedDeviceForPoints!, row.name)"
                >
                  趋势
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
      
      <el-tab-pane label="北向通道" name="north">
        <div class="section">
          <div class="section-header">
            <h3>北向通道 ({{ filteredNorthChannels.length }})</h3>
            <span class="section-desc">数据上传通道</span>
          </div>
          <el-row :gutter="20">
            <el-col 
              v-for="channel in filteredNorthChannels" 
              :key="channel.name" 
              :span="8"
            >
              <el-card class="channel-card" shadow="hover" :class="{ offline: channel.status === 'offline' }">
                <div class="channel-header">
                  <div class="channel-status" :class="channel.status">
                    <el-icon v-if="channel.status === 'online'"><CircleCheck /></el-icon>
                    <el-icon v-else><CircleClose /></el-icon>
                  </div>
                  <div class="channel-name">{{ channel.name }}</div>
                  <el-switch 
                    v-model="channel.enabled" 
                    size="small"
                    @change="handleToggleChannel(channel.name)"
                  />
                </div>
                <div class="channel-info">
                  <div class="info-row">
                    <span class="label">协议:</span>
                    <span class="value">{{ channel.protocol }}</span>
                  </div>
                  <div class="info-row">
                    <span class="label">地址:</span>
                    <span class="value">{{ channel.connection.url || `${channel.connection.host}:${channel.connection.port}` }}</span>
                  </div>
                </div>
                <div class="channel-stats">
                  <div class="stat">
                    <span class="stat-value">{{ channel.uploadedCount.toLocaleString() }}</span>
                    <span class="stat-label">已上传</span>
                  </div>
                </div>
                <div class="channel-footer">
                  <el-button type="primary" link size="small">配置</el-button>
                  <el-button type="primary" link size="small">映射</el-button>
                  <el-button type="primary" link size="small">测试</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
    
    <el-dialog 
      v-model="showDeviceDialog" 
      :title="isEditing ? '编辑设备' : '新增设备'"
      width="600px"
    >
      <el-form label-width="100px">
        <el-form-item label="设备名称">
          <el-input v-model="editingDeviceData.name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="资产名称">
          <el-input v-model="editingDeviceData.assetName" placeholder="请输入资产名称" />
        </el-form-item>
        <el-form-item label="协议类型">
          <el-select v-model="editingDeviceData.protocol" placeholder="请选择协议">
            <el-option label="KNX" value="KNX" />
            <el-option label="Modbus TCP" value="Modbus TCP" />
            <el-option label="BACnet" value="BACnet" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址">
          <el-input v-model="editingDeviceData.connection.host" placeholder="请输入主机地址" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="editingDeviceData.connection.port" :min="1" :max="65535" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeviceDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveDevice">保存</el-button>
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
        :device-name="selectedPointForTrend?.deviceName"
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

.device-card, .channel-card {
  margin-bottom: 16px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.device-card:hover, .channel-card:hover {
  transform: translateY(-2px);
}

.device-card.offline, .channel-card.offline {
  opacity: 0.7;
}

.device-card.selected {
  border: 2px solid #3498db;
  box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
}

.device-header, .channel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.device-status, .channel-status {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.device-status.online, .channel-status.online {
  background: #e8f5e9;
  color: #27ae60;
}

.device-status.offline, .channel-status.offline {
  background: #ffebee;
  color: #e74c3c;
}

.device-name, .channel-name {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.device-info, .channel-info {
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

.update-time {
  font-size: 12px;
  color: #95a5a6;
}

.actions {
  display: flex;
  gap: 4px;
}

.channel-stats {
  display: flex;
  justify-content: center;
  padding: 16px 0;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 12px;
}

.stat {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #3498db;
}

.stat-label {
  font-size: 12px;
  color: #7f8c8d;
}

.channel-footer {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.points-section {
  margin-top: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.current-value {
  font-weight: 600;
  color: #3498db;
}
</style>
