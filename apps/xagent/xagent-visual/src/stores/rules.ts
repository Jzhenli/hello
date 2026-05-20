import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Rule {
  id: string
  name: string
  description?: string
  type: 'scene' | 'alert' | 'schedule'
  enabled: boolean
  priority: number
  expression?: string
  executionCount: number
  lastTriggered?: string
  createdAt: number
  updatedAt: number
}

export interface RuleExecution {
  id: string
  ruleId: string
  ruleName: string
  triggeredAt: string
  status: 'success' | 'failed'
  duration: number
  errorMessage?: string
}

export const useRuleStore = defineStore('rules', () => {
  const rules = ref<Rule[]>([
    {
      id: 'rule-001',
      name: '温度控制规则',
      description: '温度超过30度时开启空调',
      type: 'scene',
      enabled: true,
      priority: 1,
      expression: 'temperature > 30',
      executionCount: 156,
      lastTriggered: '10分钟前',
      createdAt: Date.now() - 86400000 * 7,
      updatedAt: Date.now() - 3600000
    },
    {
      id: 'rule-002',
      name: '智能照明规则',
      description: '光照低于100且有人时开灯',
      type: 'scene',
      enabled: true,
      priority: 2,
      expression: 'light < 100 AND presence == true',
      executionCount: 89,
      lastTriggered: '1小时前',
      createdAt: Date.now() - 86400000 * 5,
      updatedAt: Date.now() - 7200000
    },
    {
      id: 'rule-003',
      name: '安防联动规则',
      description: '火灾报警时开启喷淋并发送通知',
      type: 'scene',
      enabled: false,
      priority: 0,
      expression: 'fire_alarm == true',
      executionCount: 0,
      createdAt: Date.now() - 86400000 * 3,
      updatedAt: Date.now() - 86400000
    },
    {
      id: 'rule-004',
      name: '定时开关灯',
      description: '每天18:00开启照明',
      type: 'schedule',
      enabled: true,
      priority: 3,
      expression: 'schedule: daily 18:00',
      executionCount: 45,
      lastTriggered: '昨天 18:00',
      createdAt: Date.now() - 86400000 * 10,
      updatedAt: Date.now() - 86400000
    }
  ])

  const executions = ref<RuleExecution[]>([
    {
      id: 'exec-001',
      ruleId: 'rule-001',
      ruleName: '温度控制规则',
      triggeredAt: '10:23:45',
      status: 'success',
      duration: 0.125
    },
    {
      id: 'exec-002',
      ruleId: 'rule-002',
      ruleName: '智能照明规则',
      triggeredAt: '10:15:22',
      status: 'success',
      duration: 0.089
    },
    {
      id: 'exec-003',
      ruleId: 'rule-001',
      ruleName: '温度控制规则',
      triggeredAt: '09:45:30',
      status: 'success',
      duration: 0.102
    },
    {
      id: 'exec-004',
      ruleId: 'rule-004',
      ruleName: '定时开关灯',
      triggeredAt: '昨天 18:00',
      status: 'success',
      duration: 0.056
    }
  ])

  const activeRules = computed(() => 
    rules.value.filter(r => r.enabled).length
  )
  
  const totalRules = computed(() => rules.value.length)
  
  const todayExecutions = computed(() => 
    executions.value.filter(e => !e.triggeredAt.includes('昨天')).length
  )

  const toggleRule = (id: string) => {
    const rule = rules.value.find(r => r.id === id)
    if (rule) {
      rule.enabled = !rule.enabled
      rule.updatedAt = Date.now()
    }
  }

  const deleteRule = (id: string) => {
    const index = rules.value.findIndex(r => r.id === id)
    if (index !== -1) {
      rules.value.splice(index, 1)
    }
  }

  return {
    rules,
    executions,
    activeRules,
    totalRules,
    todayExecutions,
    toggleRule,
    deleteRule
  }
})
