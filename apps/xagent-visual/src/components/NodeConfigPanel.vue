<template>
  <div class="node-config-panel">
    <div class="panel-header">
      <h3>{{ panelTitle }}</h3>
      <button class="delete-btn" @click="handleDelete" :title="t('nodeConfig.deleteNode')">
        🗑️
      </button>
    </div>
    
    <div class="panel-body">
      <!-- 数据触发器配置 -->
      <template v-if="nodeType === 'trigger' && localData.trigger">
        <div class="form-group">
          <label>{{ t('nodeConfig.dataSourceDevice') }}</label>
          <el-select
            v-model="selectedTriggerDevice"
            :placeholder="t('common.pleaseSelect', { name: t('nodeConfig.dataSourceDevice') })"
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
                <span class="device-meta">{{ device.plugin?.name }} · {{ device.points?.length || 0 }} {{ t('nodeConfig.points') }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.dataPoint') }}</label>
          <el-select
            v-model="localData.trigger.field"
            :placeholder="t('common.pleaseSelect', { name: t('nodeConfig.dataPoint') })"
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
          <label>{{ t('nodeConfig.southPlugin') }}</label>
          <div class="info-value">{{ localData.trigger.sourceService }}</div>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea
            v-model="localData.trigger.description"
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 定时触发器配置 -->
      <template v-if="nodeType === 'schedule-trigger' && localData.scheduleTrigger">
        <div class="form-group">
          <label>{{ t('nodeConfig.triggerMode') }}</label>
          <select v-model="localData.scheduleTrigger.mode" @change="updateData">
            <option v-for="mode in SCHEDULE_MODES" :key="mode.value" :value="mode.value">
              {{ t(mode.labelKey) }}
            </option>
          </select>
        </div>
        
        <template v-if="localData.scheduleTrigger.mode === 'periodic'">
          <div class="form-group">
            <label>{{ t('nodeConfig.executionFrequency') }}</label>
            <select v-model="localData.scheduleTrigger.frequency" @change="updateData">
              <option v-for="freq in SCHEDULE_FREQUENCIES" :key="freq.value" :value="freq.value">
                {{ t(freq.labelKey) }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>{{ t('nodeConfig.executionTime') }}</label>
            <input 
              v-model="localData.scheduleTrigger.time" 
              type="time" 
              @input="updateData"
            >
          </div>
          
          <div v-if="localData.scheduleTrigger.frequency === 'weekly'" class="form-group">
            <label>{{ t('nodeConfig.selectWeekday') }}</label>
            <div class="weekday-selector">
              <button 
                v-for="day in WEEKDAYS" 
                :key="day.value"
                class="weekday-btn"
                :class="{ active: isDaySelected(day.value) }"
                @click="toggleDay(day.value)"
              >
                {{ t(day.labelKey) }}
              </button>
            </div>
          </div>
        </template>
        
        <template v-if="localData.scheduleTrigger.mode === 'once'">
          <div class="form-group">
            <label>{{ t('nodeConfig.executionTime') }}</label>
            <input 
              v-model="localData.scheduleTrigger.time" 
              type="time" 
              @input="updateData"
            >
          </div>
          <div class="form-group">
            <label>{{ t('nodeConfig.executionDate') }}</label>
            <input 
              v-model="localData.scheduleTrigger.startDate" 
              type="date" 
              @input="updateData"
            >
          </div>
        </template>
        
        <template v-if="localData.scheduleTrigger.mode === 'cron'">
          <div class="form-group">
            <label>{{ t('nodeConfig.cronExpression') }}</label>
            <input 
              v-model="localData.scheduleTrigger.cron" 
              type="text" 
              :placeholder="t('nodeConfig.cronFormat')"
              @input="updateData"
            >
            <span class="hint">{{ t('nodeConfig.cronFormat') }}</span>
          </div>
          <div class="cron-examples">
            <p><strong>{{ t('nodeConfig.cronExample') }}:</strong></p>
            <p>0 0 8 * * ? - {{ t('ruleEditor.executionTime') }}8:00</p>
            <p>0 30 18 * * ? - {{ t('ruleEditor.executionTime') }}18:30</p>
            <p>0 0 9 ? * MON-FRI - {{ t('ruleEditor.executionTime') }}9:00</p>
          </div>
        </template>
        
        <div class="form-group">
          <label>{{ t('nodeConfig.effectiveDateRange') }}</label>
          <div class="date-range">
            <input 
              v-model="localData.scheduleTrigger.startDate" 
              type="date" 
              @input="updateData"
              :placeholder="t('nodeConfig.startDate')"
            >
            <span>{{ t('nodeConfig.to') }}</span>
            <input 
              v-model="localData.scheduleTrigger.endDate" 
              type="date" 
              @input="updateData"
              :placeholder="t('nodeConfig.endDate')"
            >
          </div>
        </div>
        
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea 
            v-model="localData.scheduleTrigger.description" 
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 条件判断配置 -->
      <template v-if="nodeType === 'condition' && localData.condition">
        <div class="form-group">
          <label>{{ t('nodeConfig.fieldName') }}</label>
          <el-select
            v-if="triggerPoints.length > 0"
            v-model="localData.condition.field"
            :placeholder="t('nodeConfig.selectOrEnterField')"
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
            placeholder="e.g. temperature"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.operator') }}</label>
          <select v-model="localData.condition.operator" @change="updateData">
            <option v-for="op in OPERATORS" :key="op.value" :value="op.value">
              {{ t(op.labelKey) }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.comparisonValue') }}</label>
          <input 
            v-model="localData.condition.value" 
            type="text" 
            placeholder="e.g. 30"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.duration') }}</label>
          <input 
            v-model.number="localData.condition.duration" 
            type="number" 
            min="0"
            :placeholder="t('nodeConfig.instantTrigger')"
            @input="updateData"
          >
          <span class="hint">0 = {{ t('nodeConfig.instantTrigger') }}</span>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea 
            v-model="localData.condition.description" 
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 逻辑运算配置 -->
      <template v-if="nodeType === 'logic' && localData.logic">
        <div class="form-group">
          <label>{{ t('nodeConfig.logicOperator') }}</label>
          <select v-model="localData.logic.operator" @change="updateData">
            <option v-for="op in LOGIC_OPERATORS" :key="op.value" :value="op.value">
              {{ t(op.labelKey) }}
            </option>
          </select>
        </div>
        <div class="logic-hint">
          <p><strong>AND:</strong> {{ t('nodeConfig.logicAnd') }}</p>
          <p><strong>OR:</strong> {{ t('nodeConfig.logicOr') }}</p>
          <p><strong>NOT:</strong> {{ t('nodeConfig.logicNot') }}</p>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea 
            v-model="localData.logic.description" 
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>
      
      <!-- 执行动作配置 -->
      <template v-if="nodeType === 'action' && localData.action">
        <div class="form-group">
          <label>{{ t('nodeConfig.targetDevice') }}</label>
          <el-select
            v-model="selectedActionDevice"
            :placeholder="t('common.pleaseSelect', { name: t('nodeConfig.targetDevice') })"
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
                <span class="device-meta">{{ device.plugin?.name }} · {{ device.points?.length || 0 }} {{ t('nodeConfig.points') }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.operationType') }}</label>
          <el-select
            v-model="localData.action.operation"
            :placeholder="t('common.pleaseSelect', { name: t('nodeConfig.operationType') })"
            style="width: 100%"
            @change="updateData"
          >
            <el-option :label="t('nodeConfig.writeSetpoint')" value="write_setpoint" />
            <el-option :label="t('nodeConfig.executeOperation')" value="execute_operation" />
          </el-select>
        </div>
        <template v-if="localData.action.operation === 'write_setpoint'">
          <div class="form-group">
            <label>{{ t('nodeConfig.writePoint') }}</label>
            <el-select
              v-model="selectedActionPoint"
              :placeholder="t('common.pleaseSelect', { name: t('nodeConfig.writePoint') })"
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
            <label>{{ t('nodeConfig.writeValue') }}</label>
            <input 
              v-model="actionValue"
              type="text"
              placeholder="e.g. true / 1 / 25.5"
              @input="updateData"
            >
          </div>
        </template>
        <div v-if="localData.action.targetService" class="form-group info-group">
          <label>{{ t('nodeConfig.southPlugin') }}</label>
          <div class="info-value">{{ localData.action.targetService }}</div>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.delayExecution') }}</label>
          <input 
            v-model.number="localData.action.delay" 
            type="number" 
            min="0"
            :placeholder="t('nodeConfig.immediateExecution')"
            @input="updateData"
          >
          <span class="hint">0 = {{ t('nodeConfig.immediateExecution') }}</span>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea 
            v-model="localData.action.description" 
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>

      <!-- 通知告警配置 -->
      <template v-if="nodeType === 'notification' && localData.notification">
        <div class="form-group">
          <label>{{ t('nodeConfig.notificationLevel') }}</label>
          <select v-model="localData.notification.level" @change="updateData">
            <option v-for="lv in NOTIFICATION_LEVELS" :key="lv.value" :value="lv.value">
              {{ t(lv.labelKey) }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.notificationChannel') }}</label>
          <select v-model="localData.notification.channel_type" @change="updateData">
            <option v-for="ct in NOTIFICATION_CHANNEL_TYPES" :key="ct.value" :value="ct.value">
              {{ t(ct.labelKey) }}
            </option>
          </select>
        </div>
        <div class="form-group info-box">
          <span class="info-icon">💡</span>
          <span>{{ t('nodeConfig.channelConfigHint') }}</span>
        </div>
        <div class="form-group">
          <label>{{ t('nodeConfig.description') }}</label>
          <textarea
            v-model="localData.notification.description"
            :placeholder="t('nodeConfig.optionalDesc')"
            @input="updateData"
          ></textarea>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RuleNodeData, NodeType } from '@/types/rule'
import { OPERATORS, LOGIC_OPERATORS, SCHEDULE_MODES, SCHEDULE_FREQUENCIES, WEEKDAYS, NOTIFICATION_LEVELS, NOTIFICATION_CHANNEL_TYPES } from '@/types/rule'
import { useDeviceStore } from '@/stores/devices'
import type { DeviceConfig, PointConfig } from '@/api/types'

const { t } = useI18n()

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
    trigger: t('nodeConfig.triggerTitle'),
    'schedule-trigger': t('nodeConfig.scheduleTitle'),
    condition: t('nodeConfig.conditionTitle'),
    logic: t('nodeConfig.logicTitle'),
    action: t('nodeConfig.actionTitle'),
    notification: t('nodeConfig.notificationTitle')
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

<style scoped>
.node-config-panel {
  width: 280px;
  background: var(--bg-container);
  border-left: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-base);
  background: var(--bg-hover);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text-primary);
}

.delete-btn {
  padding: 4px 8px;
  border: none;
  background: var(--color-danger);
  color: var(--text-white);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;
}

.delete-btn:hover {
  background: var(--color-danger-dark, #c0392b);
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
  color: var(--text-primary);
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-base);
  border-radius: 6px;
  font-size: 13px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.form-group textarea {
  min-height: 60px;
  resize: vertical;
}

.form-group .hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.info-group .info-value {
  padding: 8px 12px;
  background: var(--color-info-light, #f0f9ff);
  border: 1px solid var(--color-info-border, #bae6fd);
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-info-text, #0369a1);
}

.device-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.device-option .device-name {
  font-size: 13px;
  color: var(--text-primary);
}

.device-option .device-meta {
  font-size: 11px;
  color: var(--text-secondary);
}

.point-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.point-option .point-name {
  font-size: 13px;
  color: var(--text-primary);
}

.point-option .point-meta {
  font-size: 11px;
  color: var(--text-secondary);
}

.logic-hint {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: 6px;
  margin-bottom: 16px;
}

.logic-hint p {
  margin: 4px 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.weekday-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.weekday-btn {
  padding: 6px 10px;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  background: var(--bg-container);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.weekday-btn:hover {
  border-color: var(--color-primary);
}

.weekday-btn.active {
  background: var(--color-primary);
  color: var(--text-white);
  border-color: var(--color-primary);
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
  color: var(--text-secondary);
  font-size: 12px;
}

.cron-examples {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 12px;
  color: var(--text-secondary);
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
  background: var(--color-info-light, #f0f9ff);
  border: 1px solid var(--color-info-border, #bae6fd);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-info-text, #0369a1);
  line-height: 1.4;
}

.info-icon {
  flex-shrink: 0;
}
</style>
