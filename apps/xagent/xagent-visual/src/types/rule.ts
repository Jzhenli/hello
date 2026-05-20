import type { Node, Edge } from '@vue-flow/core'

export type NodeType = 
  | 'trigger' 
  | 'schedule-trigger'
  | 'condition' 
  | 'logic' 
  | 'action'

export interface TriggerData {
  source: string
  field: string
  description?: string
}

export interface ScheduleTriggerData {
  mode: 'once' | 'periodic' | 'cron'
  time: string
  frequency?: 'daily' | 'weekly' | 'monthly'
  days: number[]
  startDate?: string
  endDate?: string
  cron?: string
  description?: string
}

export interface ConditionData {
  field: string
  operator: '>' | '<' | '>=' | '<=' | '==' | '!=' | 'regex'
  value: string | number
  duration: number
  description?: string
}

export interface LogicData {
  operator: 'and' | 'or' | 'not'
  description?: string
}

export interface ActionData {
  target_asset: string
  operation: string
  parameters: Record<string, any>
  delay: number
  description?: string
}

export interface RuleNodeData {
  trigger?: TriggerData
  scheduleTrigger?: ScheduleTriggerData
  condition?: ConditionData
  logic?: LogicData
  action?: ActionData
  label?: string
}

export type RuleNode = Node<RuleNodeData>
export type RuleEdge = Edge

export interface RuleGraph {
  nodes: RuleNode[]
  edges: RuleEdge[]
}

export interface Rule {
  id: string
  name: string
  description?: string
  type: 'scene' | 'alert' | 'schedule'
  enabled: boolean
  priority: number
  graph: RuleGraph
  expression?: string
  cooldown_period?: number
  max_executions?: number
}

export interface NodeTemplate {
  type: NodeType
  label: string
  icon: string
  color: string
  category: string
  defaultData: RuleNodeData
}

export const NODE_TEMPLATES: NodeTemplate[] = [
  {
    type: 'trigger',
    label: '数据触发器',
    icon: '🎯',
    color: '#3498db',
    category: '触发器',
    defaultData: {
      trigger: {
        source: '',
        field: '',
        description: ''
      },
      label: '数据触发器'
    }
  },
  {
    type: 'schedule-trigger',
    label: '定时触发器',
    icon: '⏰',
    color: '#00bcd4',
    category: '触发器',
    defaultData: {
      scheduleTrigger: {
        mode: 'periodic',
        time: '08:00',
        frequency: 'daily',
        days: [],
        description: ''
      },
      label: '定时触发器'
    }
  },
  {
    type: 'condition',
    label: '条件判断',
    icon: '⚙️',
    color: '#9b59b6',
    category: '条件',
    defaultData: {
      condition: {
        field: '',
        operator: '>',
        value: '',
        duration: 0,
        description: ''
      },
      label: '条件判断'
    }
  },
  {
    type: 'logic',
    label: '逻辑运算',
    icon: '🔀',
    color: '#e67e22',
    category: '逻辑',
    defaultData: {
      logic: {
        operator: 'and',
        description: ''
      },
      label: '逻辑运算'
    }
  },
  {
    type: 'action',
    label: '执行动作',
    icon: '⚡',
    color: '#27ae60',
    category: '动作',
    defaultData: {
      action: {
        target_asset: '',
        operation: '',
        parameters: {},
        delay: 0,
        description: ''
      },
      label: '执行动作'
    }
  }
]

export const OPERATORS = [
  { value: '>', label: '大于 (>)' },
  { value: '<', label: '小于 (<)' },
  { value: '>=', label: '大于等于 (>=)' },
  { value: '<=', label: '小于等于 (<=)' },
  { value: '==', label: '等于 (==)' },
  { value: '!=', label: '不等于 (!=)' },
  { value: 'regex', label: '正则匹配 (=~)' }
]

export const LOGIC_OPERATORS = [
  { value: 'and', label: 'AND (与)' },
  { value: 'or', label: 'OR (或)' },
  { value: 'not', label: 'NOT (非)' }
]

export const SCHEDULE_MODES = [
  { value: 'once', label: '一次性' },
  { value: 'periodic', label: '周期性' },
  { value: 'cron', label: 'Cron表达式' }
]

export const SCHEDULE_FREQUENCIES = [
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' }
]

export const WEEKDAYS = [
  { value: 0, label: '周日' },
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' }
]
