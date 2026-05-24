<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useScadaStore } from '@/stores/scada'
import { usePointStore } from '@/stores/points'
import type { PointBinding } from '@/types/scada'

const scadaStore = useScadaStore()
const pointStore = usePointStore()

const selectedDevice = ref<string>('')
const selectedPoint = ref<string>('')

const component = computed(() => scadaStore.selectedComponent)
const currentPanel = computed(() => scadaStore.currentPanel)

const currentBinding = computed(() => component.value?.binding)

const panelWidth = ref(1200)
const panelHeight = ref(800)
const panelBgColor = ref('#f0f2f5')
const panelGrid = ref(20)

watch(currentPanel, (panel) => {
  if (panel) {
    panelWidth.value = panel.width
    panelHeight.value = panel.height
    panelBgColor.value = panel.backgroundColor
    panelGrid.value = panel.grid
  }
}, { immediate: true })

watch(currentBinding, (binding) => {
  if (binding) {
    selectedDevice.value = binding.deviceId
    selectedPoint.value = binding.pointName
  } else {
    selectedDevice.value = ''
    selectedPoint.value = ''
  }
}, { immediate: true })

const availablePoints = computed(() => {
  if (!selectedDevice.value) return []
  const device = pointStore.devices.find(d => d.asset === selectedDevice.value || d.name === selectedDevice.value)
  return device?.points || []
})

const handleDeviceChange = () => {
  selectedPoint.value = ''
}

const handlePointChange = () => {
  if (!component.value || !selectedDevice.value || !selectedPoint.value) return
  
  const point = availablePoints.value.find(p => p.name === selectedPoint.value)
  if (!point) return

  const binding: PointBinding = {
    deviceId: selectedDevice.value,
    pointName: selectedPoint.value,
    pointDescription: point.description,
    unit: point.unit
  }

  scadaStore.bindPoint(component.value.id, binding)
}

const handleUnbind = () => {
  if (!component.value) return
  scadaStore.bindPoint(component.value.id, null)
  selectedDevice.value = ''
  selectedPoint.value = ''
}

const handleDelete = () => {
  if (!component.value) return
  scadaStore.deleteComponent(component.value.id)
}

const handleDuplicate = () => {
  if (!component.value) return
  scadaStore.duplicateComponent(component.value.id)
}

const handleBringToFront = () => {
  if (!component.value) return
  scadaStore.bringToFront(component.value.id)
}

const handleSendToBack = () => {
  if (!component.value) return
  scadaStore.sendToBack(component.value.id)
}

const updateStyle = (key: string, value: any) => {
  if (!component.value) return
  scadaStore.updateComponent(component.value.id, {
    style: { ...component.value.style, [key]: value }
  })
}

const updateConfig = (configKey: string, key: string, value: any) => {
  if (!component.value) return
  const config = (component.value as any)[configKey] || {}
  scadaStore.updateComponent(component.value.id, {
    [configKey]: { ...config, [key]: value }
  })
}

const updatePanelSize = () => {
  if (!currentPanel.value) return
  scadaStore.updatePanel({
    width: panelWidth.value,
    height: panelHeight.value,
    backgroundColor: panelBgColor.value,
    grid: panelGrid.value
  })
}

const presetSizes = [
  { name: '小 (800×600)', width: 800, height: 600 },
  { name: '中 (1200×800)', width: 1200, height: 800 },
  { name: '大 (1920×1080)', width: 1920, height: 1080 },
  { name: '超宽 (2560×1080)', width: 2560, height: 1080 },
]

const applyPreset = (preset: typeof presetSizes[0]) => {
  panelWidth.value = preset.width
  panelHeight.value = preset.height
  updatePanelSize()
}
</script>

<template>
  <div class="config-panel">
    <div class="panel-header">
      <h3>⚙️ {{ component ? '组件配置' : '面板设置' }}</h3>
    </div>
    
    <div v-if="component" class="panel-body">
      <!-- 基本信息 -->
      <div class="config-section">
        <div class="section-title">基本信息</div>
        <div class="form-group">
          <label>名称</label>
          <input 
            type="text" 
            :value="component.name"
            @input="scadaStore.updateComponent(component.id, { name: ($event.target as HTMLInputElement).value })"
          >
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>X</label>
            <input type="number" :value="component.x" @input="scadaStore.moveComponent(component.id, +($event.target as HTMLInputElement).value, component.y)">
          </div>
          <div class="form-group">
            <label>Y</label>
            <input type="number" :value="component.y" @input="scadaStore.moveComponent(component.id, component.x, +($event.target as HTMLInputElement).value)">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>宽度</label>
            <input type="number" :value="component.style.width" @input="updateStyle('width', +($event.target as HTMLInputElement).value)">
          </div>
          <div class="form-group">
            <label>高度</label>
            <input type="number" :value="component.style.height" @input="updateStyle('height', +($event.target as HTMLInputElement).value)">
          </div>
        </div>
      </div>

      <!-- 点位绑定 -->
      <div class="config-section">
        <div class="section-title">点位绑定</div>
        <div class="form-group">
          <label>设备</label>
          <select v-model="selectedDevice" @change="handleDeviceChange">
            <option value="">请选择设备</option>
            <option v-for="device in pointStore.devices" :key="device.asset" :value="device.asset">
              {{ device.name }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>点位</label>
          <select v-model="selectedPoint" @change="handlePointChange">
            <option value="">请选择点位</option>
            <option v-for="point in availablePoints" :key="point.name" :value="point.name">
              {{ point.name }} ({{ point.description }})
            </option>
          </select>
        </div>
        <div v-if="currentBinding" class="binding-info">
          <div class="binding-badge">
            <span class="device">{{ currentBinding.deviceId }}</span>
            <span class="separator">/</span>
            <span class="point">{{ currentBinding.pointName }}</span>
          </div>
          <el-button type="danger" size="small" @click="handleUnbind">解除绑定</el-button>
        </div>
      </div>

      <!-- 仪表盘配置 -->
      <div v-if="component.type === 'gauge' && component.gaugeConfig" class="config-section">
        <div class="section-title">仪表盘配置</div>
        <div class="form-row">
          <div class="form-group">
            <label>最小值</label>
            <input type="number" :value="component.gaugeConfig.min" @input="updateConfig('gaugeConfig', 'min', +($event.target as HTMLInputElement).value)">
          </div>
          <div class="form-group">
            <label>最大值</label>
            <input type="number" :value="component.gaugeConfig.max" @input="updateConfig('gaugeConfig', 'max', +($event.target as HTMLInputElement).value)">
          </div>
        </div>
        <div class="form-group">
          <label>单位</label>
          <input type="text" :value="component.gaugeConfig.unit" @input="updateConfig('gaugeConfig', 'unit', ($event.target as HTMLInputElement).value)">
        </div>
      </div>

      <!-- 图表配置 -->
      <div v-if="(component.type === 'chart-line' || component.type === 'chart-bar') && component.chartConfig" class="config-section">
        <div class="section-title">图表配置</div>
        <div class="form-group">
          <label>时间范围</label>
          <select :value="component.chartConfig.timeRange" @change="updateConfig('chartConfig', 'timeRange', ($event.target as HTMLSelectElement).value)">
            <option value="1h">1小时</option>
            <option value="6h">6小时</option>
            <option value="24h">24小时</option>
            <option value="7d">7天</option>
          </select>
        </div>
        <div class="form-group">
          <label>线条颜色</label>
          <input type="color" :value="component.chartConfig.lineColor" @input="updateConfig('chartConfig', 'lineColor', ($event.target as HTMLInputElement).value)">
        </div>
      </div>

      <!-- 指示灯配置 -->
      <div v-if="component.type === 'indicator' && component.indicatorConfig" class="config-section">
        <div class="section-title">指示灯配置</div>
        <div class="form-group">
          <label>开启颜色</label>
          <input type="color" :value="component.indicatorConfig.onColor" @input="updateConfig('indicatorConfig', 'onColor', ($event.target as HTMLInputElement).value)">
        </div>
        <div class="form-group">
          <label>关闭颜色</label>
          <input type="color" :value="component.indicatorConfig.offColor" @input="updateConfig('indicatorConfig', 'offColor', ($event.target as HTMLInputElement).value)">
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="config-section">
        <div class="section-title">操作</div>
        <div class="action-buttons">
          <el-button size="small" @click="handleDuplicate">📋 复制</el-button>
          <el-button size="small" @click="handleBringToFront">⬆️ 置顶</el-button>
          <el-button size="small" @click="handleSendToBack">⬇️ 置底</el-button>
          <el-button 
            :type="component.locked ? 'success' : 'warning'" 
            size="small"
            @click="scadaStore.updateComponent(component.id, { locked: !component.locked })"
          >
            {{ component.locked ? '🔓 解锁' : '🔒 锁定' }}
          </el-button>
          <el-button type="danger" size="small" @click="handleDelete">🗑️ 删除</el-button>
        </div>
      </div>
    </div>

    <!-- 面板设置（未选中组件时显示） -->
    <div v-else-if="currentPanel" class="panel-body">
      <div class="config-section">
        <div class="section-title">画布尺寸</div>
        <div class="form-row">
          <div class="form-group">
            <label>宽度</label>
            <input type="number" v-model.number="panelWidth" min="400" max="4096" @change="updatePanelSize">
          </div>
          <div class="form-group">
            <label>高度</label>
            <input type="number" v-model.number="panelHeight" min="300" max="4096" @change="updatePanelSize">
          </div>
        </div>
        <div class="preset-buttons">
          <el-button 
            v-for="preset in presetSizes" 
            :key="preset.name"
            size="small"
            @click="applyPreset(preset)"
          >
            {{ preset.name }}
          </el-button>
        </div>
      </div>

      <div class="config-section">
        <div class="section-title">画布样式</div>
        <div class="form-group">
          <label>背景颜色</label>
          <div class="color-input">
            <input type="color" v-model="panelBgColor" @change="updatePanelSize">
            <input type="text" v-model="panelBgColor" @change="updatePanelSize" placeholder="#f0f2f5">
          </div>
        </div>
        <div class="form-group">
          <label>网格大小</label>
          <input type="number" v-model.number="panelGrid" min="10" max="50" step="5" @change="updatePanelSize">
        </div>
      </div>

      <div class="config-section">
        <div class="section-title">面板信息</div>
        <div class="info-item">
          <span class="info-label">面板名称</span>
          <span class="info-value">{{ currentPanel.name }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">组件数量</span>
          <span class="info-value">{{ currentPanel.components.length }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">画布尺寸</span>
          <span class="info-value">{{ currentPanel.width }} × {{ currentPanel.height }}</span>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <span class="empty-icon">📦</span>
      <p>选择组件进行配置</p>
    </div>
  </div>
</template>

<style scoped>
.config-panel {
  width: 280px;
  background: #fff;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 12px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  color: #2c3e50;
}

.panel-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.config-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eee;
}

.config-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #7f8c8d;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: #2c3e50;
  margin-bottom: 4px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #dce1e6;
  border-radius: 4px;
  font-size: 13px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3498db;
}

.form-row {
  display: flex;
  gap: 8px;
}

.form-row .form-group {
  flex: 1;
}

.color-input {
  display: flex;
  gap: 8px;
}

.color-input input[type="color"] {
  width: 40px;
  padding: 2px;
  cursor: pointer;
}

.color-input input[type="text"] {
  flex: 1;
}

.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.preset-buttons .el-button {
  flex: 1;
  min-width: calc(50% - 3px);
  font-size: 11px;
}

.binding-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  background: #e8f5e9;
  border-radius: 4px;
  margin-top: 8px;
}

.binding-badge {
  font-size: 12px;
}

.binding-badge .device {
  color: #27ae60;
  font-weight: 600;
}

.binding-badge .separator {
  color: #95a5a6;
  margin: 0 4px;
}

.binding-badge .point {
  color: #2c3e50;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 12px;
  color: #7f8c8d;
}

.info-value {
  font-size: 12px;
  color: #2c3e50;
  font-weight: 500;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #95a5a6;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}
</style>
