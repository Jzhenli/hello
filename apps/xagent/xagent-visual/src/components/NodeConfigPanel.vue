<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { RuleNodeData, NodeType } from '@/types/rule'
import { OPERATORS, LOGIC_OPERATORS, SCHEDULE_MODES, SCHEDULE_FREQUENCIES, WEEKDAYS, NOTIFICATION_LEVELS, NOTIFICATION_CHANNEL_TYPES } from '@/types/rule'
import { useDeviceStore } from '@/stores/devices'
import type { DeviceConfig, PointConfig } from '@/api/types'

const props = defineProps<{
  nodeId: string
  nodeType: NodeType
  nodeData: RuleNodeData
}>()

const emit = defineEmits<{
  (e: 'update', data: RuleNodeData): void
  (e: 'delete', nodeId: string): void
}>()

const deviceStore = useDeviceStore()

const localData = ref<RuleNodeData>(JSON.parse(JSON.stringify(props.nodeData || {})))

watch(() => props.nodeData, (newData) => {
  localData.value = JSON.parse(JSON.stringify(newData || {}))
}, { deep: true })

const ensureNodeData = () => {
  if (props.nodeType === 'trigger' && !localData.value.trigger) {
    localData.value.trigger = { source: '', field: '' }
  }
  if (props.nodeType === 'schedule-trigger' && !localData.value.scheduleTrigger) {
    localData.value.scheduleTrigger = { mode: 'periodic', time: '08:00', frequency: 'daily', days: [] }
  }
  if (props.nodeType === 'condition' && !localData.value.condition) {
    localData.value.condition = { field: '', operator: '>', value: '', duration: 0 }
  }
  if (props.nodeType === 'logic' && !localData.value.logic) {
    localData.value.logic = { operator: 'and' }
  }
  if (props.nodeType === 'action' && !localData.value.action) {
    localData.value.action = { target_asset: '', operation: 'write_setpoint', parameters: {}, delay: 0 }
  }
  if (props.nodeType === 'notification' && !localData.value.notification) {
    localData.value.notification = { channel_type: 'system', level: 'warning' }
  }
}

watch(() => props.nodeType, () => { ensureNodeData() }, { immediate: true })

onMounted(() => {
  if (deviceStore.devices.length === 0) {
    deviceStore.fetchDevices()
  }
})

const devices = computed<DeviceConfig[]>(() => deviceStore.devices)

const triggerDevices = computed(() =>
  devices.value.filter(d => d.enabled && d.points && d.points.length > 0)
)

const selectedTriggerDevice = computed<DeviceConfig | undefined>({
  get: () => {
    const source = localData.value.trigger?.source
    return devices.value.find(d => d.asset === source)
  },
  set: (device: DeviceConfig | undefined) => {
    if (localData.value.trigger && device) {
      localData.value.trigger.source = device.asset
      localData.value.trigger.sourceService = device.plugin?.name || ''
      localData.value.trigger.field = ''
      updateData()
    }
  }
})

const triggerPoints = computed<PointConfig[]>(() => {
  if (!selectedTriggerDevice.value) return []
  return selectedTriggerDevice.value.points?.filter(p => p.enabled) || []
})

const actionDevices = computed(() => devices.value.filter(d => d.enabled))

const selectedActionDevice = computed<DeviceConfig | undefined>({
  get: () => {
    const targetAsset = localData.value.action?.target_asset
    return devices.value.find(d => d.asset === targetAsset)
  },
  set: (device: DeviceConfig | undefined) => {
    if (localData.value.action && device) {
      localData.value.action.target_asset = device.asset
      localData.value.action.targetService = device.plugin?.name || ''
      localData.value.action.operation = 'write_setpoint'
      localData.value.action.parameters = {}
      updateData()
    }
  }
})

const actionPoints = computed<PointConfig[]>(() => {
  if (!selectedActionDevice.value) return []
  return selectedActionDevice.value.points?.filter(p => p.enabled) || []
})

const selectedActionPoint = computed<string>({
  get: () => localData.value.action?.parameters?.point || '',
  set: (val: string) => {
    if (localData.value.action) {
      localData.value.action.parameters = {
        ...localData.value.action.parameters,
        point: val,
      }
      updateData()
    }
  }
})

const actionValue = computed<string>({
  get: () => {
    const v = localData.value.action?.parameters?.value
    return v !== undefined ? String(v) : ''
  },
  set: (val: string) => {
    if (localData.value.action) {
      const numVal = Number(val)
      localData.value.action.parameters = {
        ...localData.value.action.parameters,
        value: isNaN(numVal) ? val : numVal,
      }
      updateData()
    }
  }
})

const panelTitle = computed(() => {
  const titles: Record<NodeType, string> = {
    trigger: '🎯 数据触发器配置',
    'schedule-trigger': '⏰ 定时触发器配置',
    condition: '⚙️ 条件判断配置',
    logic: '🔀 逻辑运算配置',
    action: '⚡ 执行动作配置',
    notification: '📢 通知告警配置'
  }
  return titles[props.nodeType]
})

const updateData = () => {
  emit('update', { ...localData.value })
}

const handleDelete = () => {
  emit('delete', props.nodeId)
}

const toggleDay = (day: number) => {
  if (!localData.value.scheduleTrigger) return
  const days = localData.value.scheduleTrigger.days
  const index = days.indexOf(day)
  if (index === -1) {
    days.push(day)
  } else {
    days.splice(index, 1)
  }
  updateData()
}

const isDaySelected = (day: number) => {
  return localData.value.scheduleTrigger?.days?.includes(day) || false
}
</script>

<template>
  <div class="node-config-panel">
    <div class="panel-header">
      <h3>{{ panelTitle }}</h3>
      <button class="delete-btn" @click="handleDelete" title="删除节点">
        🗑️
      </button>
    </div>
    
    <div class="panel-body">
      <!-- 数据触发器配置 -->
      <template v-if="nodeType === 'trigger' && localData.trigger">
        <div class="form-group">
          <label>数据源设备</label>
          <el-select
            v-model="selectedTriggerDevice"
            placeholder="选择设备"
            filterable
            clearable
            value-key="asset"
            style="width: 100%"
            @change="updateData"
          >
            <el-option
              v-for="device in triggerDevices"
              :key="device.asset"
              :label="`${device.name || device.asset} (${device.plugin?.name})`"
              :value="device"
            >
              <div class="device-option">
                <span class="device-name">{{ device.name || device.asset }}</span>
                <span class="device-meta">{{ device.plugin?.name }} · {{ device.points?.length || 0 }} 点位</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="form-group">
          <label>数据点位</label>
          <el-select
            v-model="localData.trigger.field"
            placeholder="选择点位"
            filterable
            clearable
            :disabled="!selectedTriggerDevice"
            style="width: 100%"
            @change="updateData"
          >
            <el-option
              v-for="point in triggerPoints"
              :key="point.name"
              :label="`${point.description || point.name}${point.unit ? ' (' + point.unit + ')' : ''}`"
              :value="point.name"
            >
              <div class="point-option">
                <span class="point-name">{{ point.name }}</span>
                <span class="point-meta">
                  {{ point.data_type }}{{ point.unit ? ' · ' + point.unit : '' }}
                </span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div v-if="localData.trigger.sourceService" class="form-group info-group">
          <label>南向插件</label>
          <div class="info-value">{{ localData.trigger.sourceService }}</div>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea
            v-model="localData.trigger.description"
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 定时触发器配置 -->
      <template v-if="nodeType === 'schedule-trigger' && localData.scheduleTrigger">
        <div class="form-group">
          <label>触发模式</label>
          <select v-model="localData.scheduleTrigger.mode" @change="updateData">
            <option v-for="mode in SCHEDULE_MODES" :key="mode.value" :value="mode.value">
              {{ mode.label }}
            </option>
          </select>
        </div>
        
        <template v-if="localData.scheduleTrigger.mode === 'periodic'">
          <div class="form-group">
            <label>执行频率</label>
            <select v-model="localData.scheduleTrigger.frequency" @change="updateData">
              <option v-for="freq in SCHEDULE_FREQUENCIES" :key="freq.value" :value="freq.value">
                {{ freq.label }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>执行时间</label>
            <input 
              v-model="localData.scheduleTrigger.time" 
              type="time" 
              @input="updateData"
            >
          </div>
          
          <div v-if="localData.scheduleTrigger.frequency === 'weekly'" class="form-group">
            <label>选择星期</label>
            <div class="weekday-selector">
              <button 
                v-for="day in WEEKDAYS" 
                :key="day.value"
                class="weekday-btn"
                :class="{ active: isDaySelected(day.value) }"
                @click="toggleDay(day.value)"
              >
                {{ day.label }}
              </button>
            </div>
          </div>
        </template>
        
        <template v-if="localData.scheduleTrigger.mode === 'once'">
          <div class="form-group">
            <label>执行时间</label>
            <input 
              v-model="localData.scheduleTrigger.time" 
              type="time" 
              @input="updateData"
            >
          </div>
          <div class="form-group">
            <label>执行日期</label>
            <input 
              v-model="localData.scheduleTrigger.startDate" 
              type="date" 
              @input="updateData"
            >
          </div>
        </template>
        
        <template v-if="localData.scheduleTrigger.mode === 'cron'">
          <div class="form-group">
            <label>Cron表达式</label>
            <input 
              v-model="localData.scheduleTrigger.cron" 
              type="text" 
              placeholder="例如: 0 0 8 * * ?"
              @input="updateData"
            >
            <span class="hint">格式: 秒 分 时 日 月 周</span>
          </div>
          <div class="cron-examples">
            <p><strong>示例:</strong></p>
            <p>0 0 8 * * ? - 每天8:00</p>
            <p>0 30 18 * * ? - 每天18:30</p>
            <p>0 0 9 ? * MON-FRI - 工作日9:00</p>
          </div>
        </template>
        
        <div class="form-group">
          <label>生效日期范围</label>
          <div class="date-range">
            <input 
              v-model="localData.scheduleTrigger.startDate" 
              type="date" 
              @input="updateData"
              placeholder="开始日期"
            >
            <span>至</span>
            <input 
              v-model="localData.scheduleTrigger.endDate" 
              type="date" 
              @input="updateData"
              placeholder="结束日期"
            >
          </div>
        </div>
        
        <div class="form-group">
          <label>描述</label>
          <textarea 
            v-model="localData.scheduleTrigger.description" 
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 条件判断配置 -->
      <template v-if="nodeType === 'condition' && localData.condition">
        <div class="form-group">
          <label>字段名</label>
          <el-select
            v-if="triggerPoints.length > 0"
            v-model="localData.condition.field"
            placeholder="选择或输入字段"
            filterable
            allow-create
            clearable
            style="width: 100%"
            @change="updateData"
          >
            <el-option
              v-for="point in triggerPoints"
              :key="point.name"
              :label="point.description || point.name"
              :value="point.name"
            />
          </el-select>
          <input
            v-else
            v-model="localData.condition.field"
            type="text"
            placeholder="例如: temperature"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>运算符</label>
          <select v-model="localData.condition.operator" @change="updateData">
            <option v-for="op in OPERATORS" :key="op.value" :value="op.value">
              {{ op.label }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>比较值</label>
          <input 
            v-model="localData.condition.value" 
            type="text" 
            placeholder="例如: 30"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>持续时间 (秒)</label>
          <input 
            v-model.number="localData.condition.duration" 
            type="number" 
            min="0"
            placeholder="0 表示即时触发"
            @input="updateData"
          >
          <span class="hint">0 = 即时触发</span>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea 
            v-model="localData.condition.description" 
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 逻辑运算配置 -->
      <template v-if="nodeType === 'logic' && localData.logic">
        <div class="form-group">
          <label>逻辑运算符</label>
          <select v-model="localData.logic.operator" @change="updateData">
            <option v-for="op in LOGIC_OPERATORS" :key="op.value" :value="op.value">
              {{ op.label }}
            </option>
          </select>
        </div>
        <div class="logic-hint">
          <p><strong>AND:</strong> 所有条件都满足</p>
          <p><strong>OR:</strong> 任一条件满足</p>
          <p><strong>NOT:</strong> 条件不满足</p>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea 
            v-model="localData.logic.description" 
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 执行动作配置 -->
      <template v-if="nodeType === 'action' && localData.action">
        <div class="form-group">
          <label>目标设备</label>
          <el-select
            v-model="selectedActionDevice"
            placeholder="选择设备"
            filterable
            clearable
            value-key="asset"
            style="width: 100%"
            @change="updateData"
          >
            <el-option
              v-for="device in actionDevices"
              :key="device.asset"
              :label="`${device.name || device.asset} (${device.plugin?.name})`"
              :value="device"
            >
              <div class="device-option">
                <span class="device-name">{{ device.name || device.asset }}</span>
                <span class="device-meta">{{ device.plugin?.name }} · {{ device.points?.length || 0 }} 点位</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="form-group">
          <label>操作类型</label>
          <el-select
            v-model="localData.action.operation"
            placeholder="选择操作"
            style="width: 100%"
            @change="updateData"
          >
            <el-option label="写入设定值" value="write_setpoint" />
            <el-option label="执行操作" value="execute_operation" />
          </el-select>
        </div>
        <template v-if="localData.action.operation === 'write_setpoint'">
          <div class="form-group">
            <label>写入点位</label>
            <el-select
              v-model="selectedActionPoint"
              placeholder="选择点位"
              filterable
              clearable
              :disabled="!selectedActionDevice"
              style="width: 100%"
              @change="updateData"
            >
              <el-option
                v-for="point in actionPoints"
                :key="point.name"
                :label="`${point.description || point.name}${point.unit ? ' (' + point.unit + ')' : ''}`"
                :value="point.name"
              >
                <div class="point-option">
                  <span class="point-name">{{ point.name }}</span>
                  <span class="point-meta">{{ point.data_type }}{{ point.unit ? ' · ' + point.unit : '' }}</span>
                </div>
              </el-option>
            </el-select>
          </div>
          <div class="form-group">
            <label>写入值</label>
            <input 
              v-model="actionValue"
              type="text"
              placeholder="例如: true / 1 / 25.5"
              @input="updateData"
            >
          </div>
        </template>
        <div v-if="localData.action.targetService" class="form-group info-group">
          <label>南向插件</label>
          <div class="info-value">{{ localData.action.targetService }}</div>
        </div>
        <div class="form-group">
          <label>延迟执行 (秒)</label>
          <input 
            v-model.number="localData.action.delay" 
            type="number" 
            min="0"
            placeholder="0 表示立即执行"
            @input="updateData"
          >
          <span class="hint">0 = 立即执行</span>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea 
            v-model="localData.action.description" 
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>

      <!-- 通知告警配置 -->
      <template v-if="nodeType === 'notification' && localData.notification">
        <div class="form-group">
          <label>告警级别</label>
          <select v-model="localData.notification.level" @change="updateData">
            <option v-for="lv in NOTIFICATION_LEVELS" :key="lv.value" :value="lv.value">
              {{ lv.label }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>通知渠道</label>
          <select v-model="localData.notification.channel_type" @change="updateData">
            <option v-for="ct in NOTIFICATION_CHANNEL_TYPES" :key="ct.value" :value="ct.value">
              {{ ct.label }}
            </option>
          </select>
        </div>
        <div class="form-group info-box">
          <span class="info-icon">💡</span>
          <span>通知渠道的详细配置（收件人、SMTP、Webhook 等）请在告警配置页面中统一管理</span>
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea
            v-model="localData.notification.description"
            placeholder="可选描述"
            @input="updateData"
          ></textarea>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.node-config-panel {
  width: 280px;
  background: #fff;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #2c3e50;
}

.delete-btn {
  padding: 4px 8px;
  border: none;
  background: #e74c3c;
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;
}

.delete-btn:hover {
  background: #c0392b;
}

.panel-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #2c3e50;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #dce1e6;
  border-radius: 6px;
  font-size: 13px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

.form-group textarea {
  min-height: 60px;
  resize: vertical;
}

.form-group .hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #95a5a6;
}

.info-group .info-value {
  padding: 8px 12px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  font-size: 13px;
  color: #0369a1;
}

.device-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.device-option .device-name {
  font-size: 13px;
  color: #2c3e50;
}

.device-option .device-meta {
  font-size: 11px;
  color: #95a5a6;
}

.point-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.point-option .point-name {
  font-size: 13px;
  color: #2c3e50;
}

.point-option .point-meta {
  font-size: 11px;
  color: #95a5a6;
}

.logic-hint {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 16px;
}

.logic-hint p {
  margin: 4px 0;
  font-size: 12px;
  color: #7f8c8d;
}

.weekday-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.weekday-btn {
  padding: 6px 10px;
  border: 1px solid #dce1e6;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.weekday-btn:hover {
  border-color: #3498db;
}

.weekday-btn.active {
  background: #3498db;
  color: #fff;
  border-color: #3498db;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-range input {
  flex: 1;
}

.date-range span {
  color: #7f8c8d;
  font-size: 12px;
}

.cron-examples {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 12px;
  color: #7f8c8d;
}

.cron-examples p {
  margin: 4px 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
}

.info-box {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  font-size: 12px;
  color: #0369a1;
  line-height: 1.4;
}

.info-icon {
  flex-shrink: 0;
}
</style>
