import type { Node, Edge } from '@vue-flow/core'

export type NodeType = 
  | 'trigger' 
  | 'schedule-trigger'
  | 'condition' 
  | 'logic' 
  | 'action'
  | 'notification'

export interface TriggerData {
  source: string
  sourceService?: string
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
  targetService?: string
  operation: string
  parameters: Record<string, any>
  delay: number
  description?: string
}

export interface NotificationData {
  channel_type: 'email' | 'webhook' | 'system'
  level: 'info' | 'warning' | 'error' | 'critical'
  recipients?: string | string[]
  smtp_host?: string
  smtp_port?: number
  smtp_user?: string
  smtp_password?: string
  from_address?: string
  use_tls?: boolean
  webhook_url?: string
  webhook_method?: string
  webhook_headers?: Record<string, string>
  retention_days?: number
  description?: string
}

export interface RuleNodeData {
  trigger?: TriggerData
  scheduleTrigger?: ScheduleTriggerData
  condition?: ConditionData
  logic?: LogicData
  action?: ActionData
  notification?: NotificationData
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
  createdAt?: number
  updatedAt?: number
  executionCount?: number
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
    label: 'ruleNodeLabels.trigger',
    icon: '🎯',
    color: '#3498db',
    category: 'ruleNodeCategories.trigger',
    defaultData: {
      trigger: {
        source: '',
        field: '',
        description: ''
      },
      label: 'ruleNodeLabels.trigger'
    }
  },
  {
    type: 'schedule-trigger',
    label: 'ruleNodeLabels.scheduleTrigger',
    icon: '⏰',
    color: '#00bcd4',
    category: 'ruleNodeCategories.trigger',
    defaultData: {
      scheduleTrigger: {
        mode: 'periodic',
        time: '08:00',
        frequency: 'daily',
        days: [],
        description: ''
      },
      label: 'ruleNodeLabels.scheduleTrigger'
    }
  },
  {
    type: 'condition',
    label: 'ruleNodeLabels.condition',
    icon: '⚙️',
    color: '#9b59b6',
    category: 'ruleNodeCategories.condition',
    defaultData: {
      condition: {
        field: '',
        operator: '>',
        value: '',
        duration: 0,
        description: ''
      },
      label: 'ruleNodeLabels.condition'
    }
  },
  {
    type: 'logic',
    label: 'ruleNodeLabels.logic',
    icon: '🔀',
    color: '#e67e22',
    category: 'ruleNodeCategories.logic',
    defaultData: {
      logic: {
        operator: 'and',
        description: ''
      },
      label: 'ruleNodeLabels.logic'
    }
  },
  {
    type: 'action',
    label: 'ruleNodeLabels.action',
    icon: '⚡',
    color: '#27ae60',
    category: 'ruleNodeCategories.action',
    defaultData: {
      action: {
        target_asset: '',
        operation: 'write_setpoint',
        parameters: {},
        delay: 0,
        description: ''
      },
      label: 'ruleNodeLabels.action'
    }
  },
  {
    type: 'notification',
    label: 'ruleNodeLabels.notification',
    icon: '📢',
    color: '#e74c3c',
    category: 'ruleNodeCategories.notification',
    defaultData: {
      notification: {
        channel_type: 'system',
        level: 'warning',
        description: ''
      },
      label: 'ruleNodeLabels.notification'
    }
  }
]

export const OPERATORS = [
  { value: '>', labelKey: 'operators.gt' },
  { value: '<', labelKey: 'operators.lt' },
  { value: '>=', labelKey: 'operators.gte' },
  { value: '<=', labelKey: 'operators.lte' },
  { value: '==', labelKey: 'operators.eq' },
  { value: '!=', labelKey: 'operators.neq' },
  { value: 'regex', labelKey: 'operators.regex' }
]

export const LOGIC_OPERATORS = [
  { value: 'and', labelKey: 'logicOperators.and' },
  { value: 'or', labelKey: 'logicOperators.or' },
  { value: 'not', labelKey: 'logicOperators.not' }
]

export const NOTIFICATION_LEVELS = [
  { value: 'info', labelKey: 'notificationLevels.info', color: '#3b82f6' },
  { value: 'warning', labelKey: 'notificationLevels.warning', color: '#f59e0b' },
  { value: 'error', labelKey: 'notificationLevels.error', color: '#ef4444' },
  { value: 'critical', labelKey: 'notificationLevels.critical', color: '#dc2626' }
]

export const NOTIFICATION_CHANNEL_TYPES = [
  { value: 'system', labelKey: 'notificationChannels.system' },
  { value: 'email', labelKey: 'notificationChannels.email' },
  { value: 'webhook', labelKey: 'notificationChannels.webhook' }
]

export const SCHEDULE_MODES = [
  { value: 'once', labelKey: 'scheduleModes.once' },
  { value: 'periodic', labelKey: 'scheduleModes.periodic' },
  { value: 'cron', labelKey: 'scheduleModes.cron' }
]

export const SCHEDULE_FREQUENCIES = [
  { value: 'daily', labelKey: 'scheduleFrequencies.daily' },
  { value: 'weekly', labelKey: 'scheduleFrequencies.weekly' },
  { value: 'monthly', labelKey: 'scheduleFrequencies.monthly' }
]

export const WEEKDAYS = [
  { value: 0, labelKey: 'weekdays.sun' },
  { value: 1, labelKey: 'weekdays.mon' },
  { value: 2, labelKey: 'weekdays.tue' },
  { value: 3, labelKey: 'weekdays.wed' },
  { value: 4, labelKey: 'weekdays.thu' },
  { value: 5, labelKey: 'weekdays.fri' },
  { value: 6, labelKey: 'weekdays.sat' }
]
