<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { RuleNodeData, NodeType, ConditionData, LogicData, ActionData, TriggerData, ScheduleTriggerData } from '@/types/rule'
import { OPERATORS, LOGIC_OPERATORS, SCHEDULE_MODES, SCHEDULE_FREQUENCIES, WEEKDAYS } from '@/types/rule'

const props = defineProps<{
  nodeId: string
  nodeType: NodeType
  nodeData: RuleNodeData
}>()

const emit = defineEmits<{
  (e: 'update', data: RuleNodeData): void
  (e: 'delete', nodeId: string): void
}>()

const localData = ref<RuleNodeData>(JSON.parse(JSON.stringify(props.nodeData)))

watch(() => props.nodeData, (newData) => {
  localData.value = JSON.parse(JSON.stringify(newData))
}, { deep: true })

const panelTitle = computed(() => {
  const titles: Record<NodeType, string> = {
    trigger: '🎯 数据触发器配置',
    'schedule-trigger': '⏰ 定时触发器配置',
    condition: '⚙️ 条件判断配置',
    logic: '🔀 逻辑运算配置',
    action: '⚡ 执行动作配置'
  }
  return titles[props.nodeType]
})

const updateData = () => {
  emit('update', { ...localData.value })
}

const handleDelete = () => {
  emit('delete', props.nodeId)
}

const selectedDays = computed({
  get: () => localData.value.scheduleTrigger?.days || [],
  set: (val) => {
    if (localData.value.scheduleTrigger) {
      localData.value.scheduleTrigger.days = val
      updateData()
    }
  }
})

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
          <label>数据源</label>
          <input 
            v-model="localData.trigger.source" 
            type="text" 
            placeholder="例如: temperature_sensor"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>字段名</label>
          <input 
            v-model="localData.trigger.field" 
            type="text" 
            placeholder="例如: temperature"
            @input="updateData"
          >
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
          <input 
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
          <input 
            v-model="localData.action.target_asset" 
            type="text" 
            placeholder="例如: air_conditioner"
            @input="updateData"
          >
        </div>
        <div class="form-group">
          <label>操作类型</label>
          <input 
            v-model="localData.action.operation" 
            type="text" 
            placeholder="例如: write_setpoint"
            @input="updateData"
          >
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
          <label>参数 (JSON)</label>
          <textarea 
            v-model="localData.action.parameters"
            placeholder='{"point": "power", "value": 1}'
            @input="updateData"
          ></textarea>
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
</style>
