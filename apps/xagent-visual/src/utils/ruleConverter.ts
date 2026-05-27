import type { RuleNode, RuleEdge, Rule, RuleNodeData, NodeType } from '@/types/rule'

function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

function uuidv4(): string {
  return generateUUID()
}

export function generateNodeId(type: NodeType): string {
  return `${type}-${generateUUID().slice(0, 8)}`
}

export function createNode(
  type: NodeType, 
  position: { x: number; y: number },
  data?: Partial<RuleNodeData>
): RuleNode {
  const defaultData: Record<NodeType, RuleNodeData> = {
    trigger: { trigger: { source: '', field: '' }, label: '数据触发器' },
    'schedule-trigger': { 
      scheduleTrigger: { 
        mode: 'periodic', 
        time: '08:00', 
        frequency: 'daily', 
        days: [] 
      }, 
      label: '定时触发器' 
    },
    condition: { condition: { field: '', operator: '>', value: '', duration: 0 }, label: '条件判断' },
    logic: { logic: { operator: 'and' }, label: '逻辑运算' },
    action: { action: { target_asset: '', operation: '', parameters: {}, delay: 0 }, label: '执行动作' },
    notification: { 
      notification: { 
        channel_type: 'system', 
        level: 'warning', 
        recipients: '', 
        retention_days: 30 
      }, 
      label: '通知告警' 
    }
  }

  return {
    id: generateNodeId(type),
    type,
    position,
    data: { ...defaultData[type], ...data }
  }
}

export function graphToExpression(nodes: RuleNode[]): string {
  if (nodes.length === 0) return ''
  
  const triggerNodes = nodes.filter(n => n.type === 'trigger' || n.type === 'schedule-trigger')
  const conditionNodes = nodes.filter(n => n.type === 'condition')
  const logicNodes = nodes.filter(n => n.type === 'logic')
  const actionNodes = nodes.filter(n => n.type === 'action')
  
  const parts: string[] = []
  
  // 处理触发器
  triggerNodes.forEach(node => {
    if (node.type === 'schedule-trigger' && node.data?.scheduleTrigger) {
      const schedule = node.data?.scheduleTrigger
      if (schedule.mode === 'cron') {
        parts.push(`schedule: cron "${schedule.cron}"`)
      } else if (schedule.mode === 'once') {
        parts.push(`schedule: once at ${schedule.time} on ${schedule.startDate}`)
      } else {
        const freqMap: Record<string, string> = {
          daily: 'daily',
          weekly: 'weekly',
          monthly: 'monthly'
        }
        const freq = freqMap[schedule.frequency || 'daily']
        parts.push(`schedule: ${freq} at ${schedule.time}`)
      }
    } else if (node.type === 'trigger' && node.data?.trigger) {
      const trigger = node.data?.trigger
      if (trigger.source && trigger.field) {
        parts.push(`trigger: ${trigger.source}.${trigger.field}`)
      }
    }
  })
  
  // 处理条件
  const conditionExprs: string[] = []
  conditionNodes.forEach(node => {
    const cond = node.data?.condition
    if (cond && cond.field && cond.value) {
      let expr = ''
      if (cond.operator === 'regex') {
        expr = `${cond.field} =~ "${cond.value}"`
      } else {
        expr = `${cond.field} ${cond.operator} ${cond.value}`
      }
      conditionExprs.push(expr)
    }
  })
  
  if (conditionExprs.length > 0) {
    if (logicNodes.length > 0 && conditionExprs.length > 1) {
      const logicNode = logicNodes[0]
      const op = logicNode.data?.logic?.operator || 'and'
      
      if (op === 'not') {
        parts.push(`not (${conditionExprs.join(' and ')})`)
      } else {
        parts.push(conditionExprs.join(` ${op} `))
      }
    } else {
      parts.push(conditionExprs.join(' and '))
    }
  }
  
  // 处理动作
  actionNodes.forEach(node => {
    const action = node.data?.action
    if (action && action.target_asset && action.operation) {
      parts.push(`action: ${action.target_asset}.${action.operation}`)
    }
  })
  
  return parts.join(' -> ')
}

export function validateGraph(nodes: RuleNode[], edges: RuleEdge[]): { 
  valid: boolean
  errors: string[]
} {
  const errors: string[] = []
  
  if (nodes.length === 0) {
    errors.push('画布为空，请添加节点')
    return { valid: false, errors }
  }
  
  const triggerNodes = nodes.filter(n => n.type === 'trigger' || n.type === 'schedule-trigger')
  const conditionNodes = nodes.filter(n => n.type === 'condition')
  const actionNodes = nodes.filter(n => n.type === 'action')
  const notificationNodes = nodes.filter(n => n.type === 'notification')
  
  if (triggerNodes.length === 0) {
    errors.push('缺少触发器节点')
  }
  
  if (actionNodes.length === 0 && notificationNodes.length === 0) {
    errors.push('缺少执行动作或通知告警节点')
  }
  
  // 验证定时触发器
  triggerNodes.forEach(node => {
    if (node.type === 'schedule-trigger') {
      const schedule = node.data?.scheduleTrigger
      if (!schedule?.time && schedule?.mode !== 'cron') {
        errors.push(`定时触发器 "${node.id}" 缺少执行时间`)
      }
      if (schedule?.mode === 'cron' && !schedule.cron) {
        errors.push(`定时触发器 "${node.id}" 缺少Cron表达式`)
      }
    } else if (node.type === 'trigger') {
      const trigger = node.data?.trigger
      if (!trigger?.source) {
        errors.push(`数据触发器 "${node.id}" 缺少数据源`)
      }
      if (!trigger?.field) {
        errors.push(`数据触发器 "${node.id}" 缺少字段名`)
      }
    }
  })
  
  conditionNodes.forEach(node => {
    const cond = node.data?.condition
    if (!cond?.field) {
      errors.push(`条件节点 "${node.id}" 缺少字段名`)
    }
    if (!cond?.value && cond?.value !== 0) {
      errors.push(`条件节点 "${node.id}" 缺少比较值`)
    }
  })
  
  actionNodes.forEach(node => {
    const action = node.data?.action
    if (!action?.target_asset) {
      errors.push(`动作节点 "${node.id}" 缺少目标设备`)
    }
    if (!action?.operation) {
      errors.push(`动作节点 "${node.id}" 缺少操作类型`)
    }
  })

  notificationNodes.forEach(node => {
    const notif = node.data?.notification
    if (!notif?.channel_type) {
      errors.push(`通知节点 "${node.id}" 缺少通知渠道`)
    }
    if (notif?.channel_type !== 'system' && !notif?.recipients) {
      errors.push(`通知节点 "${node.id}" 缺少收件人`)
    }
    if (notif?.channel_type === 'email' && !notif.smtp_host) {
      errors.push(`通知节点 "${node.id}" 缺少SMTP服务器`)
    }
    if (notif?.channel_type === 'webhook' && !notif.webhook_url) {
      errors.push(`通知节点 "${node.id}" 缺少Webhook URL`)
    }
  })
  
  if (edges.length === 0 && nodes.length > 1) {
    errors.push('节点之间没有连线')
  }
  
  return { valid: errors.length === 0, errors }
}

export function exportRule(nodes: RuleNode[], edges: RuleEdge[]): Rule {
  const expression = graphToExpression(nodes)
  
  // 判断规则类型
  const hasScheduleTrigger = nodes.some(n => n.type === 'schedule-trigger')
  const ruleType = hasScheduleTrigger ? 'schedule' : 'scene'
  
  return {
    id: uuidv4(),
    name: '新规则',
    description: '通过可视化编辑器创建的规则',
    type: ruleType,
    enabled: true,
    priority: 10,
    graph: { nodes, edges },
    expression,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    executionCount: 0
  }
}

export function importRule(rule: Rule): { nodes: RuleNode[], edges: RuleEdge[] } {
  return {
    nodes: rule.graph.nodes,
    edges: rule.graph.edges
  }
}

export function createDefaultRule(): { nodes: RuleNode[], edges: RuleEdge[] } {
  const triggerNode = createNode('trigger', { x: 250, y: 50 })
  const conditionNode = createNode('condition', { x: 250, y: 180 })
  const actionNode = createNode('action', { x: 250, y: 340 })
  
  triggerNode.data!.trigger = {
    source: 'temperature_sensor',
    field: 'temperature',
    description: '温度传感器'
  }
  
  conditionNode.data!.condition = {
    field: 'temperature',
    operator: '>',
    value: '30',
    duration: 300,
    description: '温度超过30度持续5分钟'
  }
  
  actionNode.data!.action = {
    target_asset: 'air_conditioner',
    operation: 'write_setpoint',
    parameters: { point: 'power', value: 1 },
    delay: 0,
    description: '开启空调'
  }
  
  const edges: RuleEdge[] = [
    {
      id: 'e-trigger-condition',
      source: triggerNode.id,
      target: conditionNode.id,
      type: 'smoothstep',
      animated: true
    },
    {
      id: 'e-condition-action',
      source: conditionNode.id,
      target: actionNode.id,
      type: 'smoothstep',
      animated: true
    }
  ]
  
  return { nodes: [triggerNode, conditionNode, actionNode], edges }
}

export function createScheduleRule(): { nodes: RuleNode[], edges: RuleEdge[] } {
  const scheduleNode = createNode('schedule-trigger', { x: 250, y: 50 })
  const actionNode = createNode('action', { x: 250, y: 180 })
  
  scheduleNode.data!.scheduleTrigger = {
    mode: 'periodic',
    time: '18:00',
    frequency: 'daily',
    days: [],
    description: '每天18:00执行'
  }
  
  actionNode.data!.action = {
    target_asset: 'lighting_system',
    operation: 'turn_on',
    parameters: { zone: 'office' },
    delay: 0,
    description: '开启照明'
  }
  
  const edges: RuleEdge[] = [
    {
      id: 'e-schedule-action',
      source: scheduleNode.id,
      target: actionNode.id,
      type: 'smoothstep',
      animated: true
    }
  ]
  
  return { nodes: [scheduleNode, actionNode], edges }
}
