import type { RuleNode, RuleEdge, NodeType } from '@/types/rule'
import type {
  RuleResponse,
  RuleCreateRequest,
  RuleUpdateRequest,
  RulePluginConfig,
  RuleDataSubscription,
  RuleNotificationConfig
} from '@/api/types'
import { graphToExpression } from './ruleConverter'

const VISUAL_GRAPH_KEY = '_visual_graph'

export interface RuleViewItem {
  id: string
  name: string
  description?: string
  type: 'scene' | 'alert' | 'schedule'
  enabled: boolean
  priority: number
  expression?: string
  executionCount: number
  lastTriggered?: string
  plugin?: RulePluginConfig
  data_subscriptions?: RuleDataSubscription[]
  notification?: RuleNotificationConfig
  pipeline_id?: string
  channel_ids?: string[]
}

export interface ActionChannelConfig {
  target_service: string
  target_asset: string
  operation: string
  point?: string
  value?: any
  parameters?: Record<string, any>
  delay?: number
}

export interface NotificationChannelConfig {
  channel_type: 'email' | 'webhook' | 'system'
  level: 'info' | 'warning' | 'error' | 'critical'
  recipients: string[]
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
}

function extractRuleType(rule: RuleResponse): 'scene' | 'alert' | 'schedule' {
  const pluginConfig = rule.plugin?.config || {}
  const visualGraph = pluginConfig[VISUAL_GRAPH_KEY]

  if (visualGraph?.nodes) {
    const hasScheduleTrigger = visualGraph.nodes.some(
      (n: any) => n.type === 'schedule-trigger'
    )
    if (hasScheduleTrigger) return 'schedule'

    const hasNotification = visualGraph.nodes.some(
      (n: any) => n.type === 'notification'
    )
    if (hasNotification) return 'alert'
  }

  if (rule.plugin?.name === 'schedule_rule') {
    return 'schedule'
  }

  if (rule.plugin?.name === 'expression_rule') {
    return 'alert'
  }

  if (rule.data_subscriptions && rule.data_subscriptions.length > 0) {
    return 'scene'
  }

  return 'scene'
}

function extractExpression(rule: RuleResponse): string {
  const pluginConfig = rule.plugin?.config || {}
  const visualGraph = pluginConfig[VISUAL_GRAPH_KEY]

  if (visualGraph?.nodes && visualGraph.edges) {
    return graphToExpression(visualGraph.nodes)
  }

  if (rule.plugin?.name === 'schedule_rule') {
    const triggerType = rule.plugin.config.trigger_type
    if (triggerType === 'cron') {
      return `cron: ${rule.plugin.config.cron}`
    }
    return `每 ${rule.plugin.config.interval || 60} 秒`
  }

  if (rule.plugin?.name === 'threshold_rule') {
    const { threshold, operator } = rule.plugin.config
    return `value ${operator || '>'} ${threshold}`
  }

  if (rule.plugin?.name === 'expression_rule') {
    return rule.plugin.config.expression || ''
  }

  return ''
}

export function backendToViewItem(rule: RuleResponse): RuleViewItem {
  return {
    id: rule.id,
    name: rule.name,
    description: rule.description,
    type: extractRuleType(rule),
    enabled: rule.enabled,
    priority: 10,
    expression: extractExpression(rule),
    executionCount: rule.execution_count ?? 0,
    lastTriggered: rule.last_triggered
      ? new Date(rule.last_triggered * 1000).toLocaleString('zh-CN')
      : undefined,
    plugin: rule.plugin,
    data_subscriptions: rule.data_subscriptions,
    notification: rule.notification,
    pipeline_id: rule.pipeline_id,
    channel_ids: rule.channel_ids,
  }
}

function buildExpressionFromConditions(
  conditionNodes: RuleNode[],
  logicNodes: RuleNode[]
): string {
  const parts: string[] = []

  for (const node of conditionNodes) {
    const cond = node.data?.condition
    if (!cond?.field) continue

    if (cond.operator === 'regex') {
      parts.push(`${cond.field} =~ "${cond.value}"`)
    } else {
      parts.push(`${cond.field} ${cond.operator} ${cond.value}`)
    }
  }

  if (logicNodes.length > 0 && parts.length > 1) {
    const logicOp = logicNodes[0].data?.logic?.operator || 'and'
    if (logicOp === 'not') {
      return `not (${parts.join(' and ')})`
    }
    return parts.join(` ${logicOp} `)
  }

  return parts.join(' and ')
}

function buildScheduleConfig(scheduleNodes: RuleNode[]): Record<string, any> {
  if (scheduleNodes.length === 0) return {}

  const nodeData = scheduleNodes[0].data
  const schedule = nodeData?.scheduleTrigger
  if (!schedule) return { trigger_type: 'interval', interval: 60 }

  const mode = schedule.mode || 'periodic'

  if (mode === 'cron' && schedule.cron) {
    return {
      trigger_type: 'cron',
      cron: schedule.cron,
    }
  }

  if (mode === 'once' && schedule.time) {
    const startDate = schedule.startDate
    if (startDate) {
      const dt = new Date(`${startDate}T${schedule.time}`)
      return {
        trigger_type: 'cron',
        cron: `${dt.getSeconds()} ${dt.getMinutes()} ${dt.getHours()} ${dt.getDate()} ${dt.getMonth() + 1} ?`,
      }
    }
    const [hours, minutes] = schedule.time.split(':').map(Number)
    return {
      trigger_type: 'cron',
      cron: `0 ${minutes} ${hours} * * ?`,
    }
  }

  const frequency = schedule.frequency || 'daily'
  const time = schedule.time || '08:00'
  const [hours, minutes] = time.split(':').map(Number)
  const days = schedule.days || []

  if (frequency === 'daily') {
    return {
      trigger_type: 'cron',
      cron: `0 ${minutes} ${hours} * * ?`,
    }
  }

  if (frequency === 'weekly' && days.length > 0) {
    const dow = days.join(',')
    return {
      trigger_type: 'cron',
      cron: `0 ${minutes} ${hours} ? * ${dow}`,
    }
  }

  return {
    trigger_type: 'interval',
    interval: 60,
  }
}

function buildActionChannelConfig(actionNodes: RuleNode[]): ActionChannelConfig | null {
  if (actionNodes.length === 0) return null

  const action = actionNodes[0].data?.action
  if (!action) return null

  return {
    target_service: action.targetService || action.target_asset || '',
    target_asset: action.target_asset || '',
    operation: action.operation || 'write_setpoint',
    point: action.parameters?.point || '',
    value: action.parameters?.value,
    parameters: action.parameters || {},
    delay: action.delay || 0,
  }
}

function buildNotificationChannelConfig(notificationNodes: RuleNode[]): NotificationChannelConfig | null {
  if (notificationNodes.length === 0) return null

  const notif = notificationNodes[0].data?.notification
  if (!notif) return null

  return {
    channel_type: notif.channel_type || 'system',
    level: notif.level || 'warning',
    recipients: [],
  }
}

function serializeGraph(nodes: RuleNode[], edges: RuleEdge[]) {
  const serializableNodes = nodes.map(n => ({
    id: n.id,
    type: n.type,
    position: n.position,
    data: n.data,
    label: n.label,
  }))

  const serializableEdges = edges.map(e => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: e.type,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
  }))

  return { nodes: serializableNodes, edges: serializableEdges }
}

export function graphToBackendCreate(
  name: string,
  description: string,
  nodes: RuleNode[],
  edges: RuleEdge[],
  existingId?: string
): RuleCreateRequest {
  const triggerNodes = nodes.filter(n => n.type === 'trigger')
  const scheduleTriggerNodes = nodes.filter(n => n.type === 'schedule-trigger')
  const conditionNodes = nodes.filter(n => n.type === 'condition')
  const logicNodes = nodes.filter(n => n.type === 'logic')
  const actionNodes = nodes.filter(n => n.type === 'action')
  const notificationNodes = nodes.filter(n => n.type === 'notification')

  const dataSubscriptions: RuleDataSubscription[] = triggerNodes
    .filter(n => n.data?.trigger?.source && n.data?.trigger?.field)
    .map(n => ({
      asset: n.data!.trigger!.source,
      point: n.data!.trigger!.field,
      mode: 'single' as const,
    }))

  const graphData = serializeGraph(nodes, edges)

  const isScheduleRule = scheduleTriggerNodes.length > 0 && triggerNodes.length === 0

  let plugin: RulePluginConfig

  if (isScheduleRule) {
    const scheduleConfig = buildScheduleConfig(scheduleTriggerNodes)
    plugin = {
      name: 'schedule_rule',
      config: {
        ...scheduleConfig,
        [VISUAL_GRAPH_KEY]: graphData,
      },
    }
  } else if (conditionNodes.length === 1 && logicNodes.length === 0) {
    const cond = conditionNodes[0].data?.condition
    if (!cond) {
      plugin = {
        name: 'threshold_rule',
        config: {
          threshold: 0,
          operator: '>',
          duration: 0,
          [VISUAL_GRAPH_KEY]: graphData,
        },
      }
    } else {
      plugin = {
        name: 'threshold_rule',
        config: {
          threshold: Number(cond.value) || cond.value,
          operator: cond.operator,
          duration: cond.duration || 0,
          [VISUAL_GRAPH_KEY]: graphData,
        },
      }
    }
  } else if (conditionNodes.length > 0) {
    const expression = buildExpressionFromConditions(conditionNodes, logicNodes)
    plugin = {
      name: 'expression_rule',
      config: {
        expression,
        duration: 0,
        [VISUAL_GRAPH_KEY]: graphData,
      },
    }
  } else {
    plugin = {
      name: scheduleTriggerNodes.length > 0 ? 'schedule_rule' : 'threshold_rule',
      config: {
        trigger_type: 'interval',
        interval: 60,
        expression: 'true',
        duration: 0,
        [VISUAL_GRAPH_KEY]: graphData,
      },
    }
  }

  let notification: RuleNotificationConfig | undefined
  const actionConfig = buildActionChannelConfig(actionNodes)
  const notifConfig = buildNotificationChannelConfig(notificationNodes)

  if (notifConfig) {
    notification = {
      title: `${name} 触发通知`,
      message: notifConfig.channel_type === 'email'
        ? `规则 ${name} 已触发`
        : `规则 ${name} 已触发`,
      level: notifConfig.level,
      recipients: notifConfig.recipients,
    }
  } else if (actionConfig) {
    notification = {
      title: `${name} 触发通知`,
      message: `执行 ${actionConfig.target_asset}.${actionConfig.operation}`,
      level: 'warning',
    }
  }

  const ruleId = existingId || `rule-${Date.now()}`
  const channelIds: string[] = []

  if (actionConfig && actionConfig.target_service) {
    channelIds.push(`action-${ruleId}`)
  }

  if (notifConfig) {
    channelIds.push(`${notifConfig.channel_type}-${ruleId}`)
  }

  return {
    id: ruleId,
    name,
    description: description || undefined,
    enabled: true,
    plugin,
    data_subscriptions: dataSubscriptions.length > 0 ? dataSubscriptions : undefined,
    notification,
    channel_ids: channelIds.length > 0 ? channelIds : undefined,
  }
}

export function getActionChannelCreate(
  ruleId: string,
  actionNodes: RuleNode[]
): { channel_id: string; plugin_name: string; config: ActionChannelConfig } | null {
  const actionConfig = buildActionChannelConfig(actionNodes)
  if (!actionConfig || !actionConfig.target_service) return null

  return {
    channel_id: `action-${ruleId}`,
    plugin_name: 'action',
    config: actionConfig,
  }
}

export function getNotificationChannelCreate(
  ruleId: string,
  notificationNodes: RuleNode[]
): { channel_id: string; plugin_name: string; config: NotificationChannelConfig } | null {
  const notifConfig = buildNotificationChannelConfig(notificationNodes)
  if (!notifConfig) return null

  return {
    channel_id: `${notifConfig.channel_type}-${ruleId}`,
    plugin_name: notifConfig.channel_type,
    config: notifConfig,
  }
}

export function graphToBackendUpdate(
  name: string,
  description: string,
  nodes: RuleNode[],
  edges: RuleEdge[],
  currentEnabled: boolean
): RuleUpdateRequest {
  const createReq = graphToBackendCreate(name, description, nodes, edges)
  return {
    name: createReq.name,
    description: createReq.description,
    enabled: currentEnabled,
    plugin: createReq.plugin,
    data_subscriptions: createReq.data_subscriptions,
    notification: createReq.notification,
    channel_ids: createReq.channel_ids,
  }
}

export function backendToGraph(
  rule: RuleResponse
): { nodes: RuleNode[]; edges: RuleEdge[]; name: string; description: string } | null {
  const pluginConfig = rule.plugin?.config || {}
  const visualGraph = pluginConfig[VISUAL_GRAPH_KEY]

  if (visualGraph?.nodes && visualGraph.edges) {
    const nodes: RuleNode[] = visualGraph.nodes.map((n: any) => ({
      id: n.id,
      type: n.type as NodeType,
      position: n.position || { x: 0, y: 0 },
      data: n.data || {},
      label: n.label,
    }))

    const edges: RuleEdge[] = visualGraph.edges.map((e: any) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type || 'smoothstep',
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
      animated: true,
    }))

    return {
      nodes,
      edges,
      name: rule.name,
      description: rule.description || '',
    }
  }

  return reconstructGraphFromBackend(rule)
}

function reconstructGraphFromBackend(
  rule: RuleResponse
): { nodes: RuleNode[]; edges: RuleEdge[]; name: string; description: string } {
  const nodes: RuleNode[] = []
  const edges: RuleEdge[] = []
  let yOffset = 50

  if (rule.plugin?.name === 'schedule_rule') {
    const config = rule.plugin.config
    const triggerType = config.trigger_type || 'interval'

    nodes.push({
      id: 'schedule-trigger-0',
      type: 'schedule-trigger',
      position: { x: 250, y: yOffset },
      data: {
        scheduleTrigger: {
          mode: triggerType === 'cron' ? 'cron' : 'periodic',
          cron: config.cron || '',
          frequency: 'daily',
          time: '08:00',
          days: [],
          description: '',
        },
        label: '定时触发器',
      },
    })
    yOffset += 150
  } else if (rule.data_subscriptions && rule.data_subscriptions.length > 0) {
    for (const sub of rule.data_subscriptions) {
      const nodeId = `trigger-${nodes.length}`
      nodes.push({
        id: nodeId,
        type: 'trigger',
        position: { x: 250, y: yOffset },
        data: {
          trigger: {
            source: sub.asset,
            field: sub.point,
            description: '',
          },
          label: '数据触发器',
        },
      })
      yOffset += 150
    }
  }

  if (rule.plugin && rule.plugin.name !== 'schedule_rule') {
    const condNodeId = `condition-${nodes.length}`
    const pluginName = rule.plugin.name
    const config = rule.plugin.config

    if (pluginName === 'threshold_rule') {
      nodes.push({
        id: condNodeId,
        type: 'condition',
        position: { x: 250, y: yOffset },
        data: {
          condition: {
            field: 'value',
            operator: config.operator || '>',
            value: config.threshold ?? 0,
            duration: config.duration || 0,
            description: '',
          },
          label: '条件判断',
        },
      })
    } else if (pluginName === 'expression_rule') {
      nodes.push({
        id: condNodeId,
        type: 'condition',
        position: { x: 250, y: yOffset },
        data: {
          condition: {
            field: 'value',
            operator: '>',
            value: config.expression || 'true',
            duration: config.duration || 0,
            description: `表达式: ${config.expression || 'true'}`,
          },
          label: '条件判断',
        },
      })
    }

    if (nodes.length >= 2) {
      const prevNode = nodes[nodes.length - 2]
      edges.push({
        id: `e-${prevNode.id}-${condNodeId}`,
        source: prevNode.id,
        target: condNodeId,
        type: 'smoothstep',
        animated: true,
      })
    }

    yOffset += 150
  }

  if (rule.notification) {
    const channelIds = rule.channel_ids || []
    const hasActionChannel = channelIds.some(id => id.startsWith('action-'))
    const hasNotifChannel = channelIds.some(id => id.startsWith('email-') || id.startsWith('webhook-') || id.startsWith('system-'))

    if (hasNotifChannel && !hasActionChannel) {
      const notifNodeId = `notification-${nodes.length}`
      const notifChannelId = channelIds.find(id => id.startsWith('email-') || id.startsWith('webhook-') || id.startsWith('system-')) || ''
      const channelType = notifChannelId.startsWith('email-') ? 'email' : notifChannelId.startsWith('webhook-') ? 'webhook' : 'system'
      nodes.push({
        id: notifNodeId,
        type: 'notification',
        position: { x: 250, y: yOffset },
        data: {
          notification: {
            channel_type: channelType as 'email' | 'webhook' | 'system',
            level: rule.notification.level || 'warning',
            recipients: (rule.notification.recipients || []).join(', '),
            description: rule.notification.message || '',
          },
          label: '通知告警',
        },
      })

      if (nodes.length >= 2) {
        const prevNode = nodes[nodes.length - 2]
        edges.push({
          id: `e-${prevNode.id}-${notifNodeId}`,
          source: prevNode.id,
          target: notifNodeId,
          type: 'smoothstep',
          animated: true,
        })
      }
    } else {
      const actionNodeId = `action-${nodes.length}`
      nodes.push({
        id: actionNodeId,
        type: 'action',
        position: { x: 250, y: yOffset },
        data: {
          action: {
            target_asset: '',
            operation: '',
            parameters: {},
            delay: 0,
            description: rule.notification.message || '',
          },
          label: '执行动作',
        },
      })

      if (nodes.length >= 2) {
        const prevNode = nodes[nodes.length - 2]
        edges.push({
          id: `e-${prevNode.id}-${actionNodeId}`,
          source: prevNode.id,
          target: actionNodeId,
          type: 'smoothstep',
          animated: true,
        })
      }
    }
  }

  return {
    nodes,
    edges,
    name: rule.name,
    description: rule.description || '',
  }
}
