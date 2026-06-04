import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ruleApi } from '@/api/rules'
import type { AlertResponse } from '@/api/types'

export interface Alert {
  id: string
  ruleId: string
  ruleName: string
  level: 'critical' | 'warning' | 'info'
  status: 'new' | 'acknowledged' | 'resolved' | 'ignored'
  asset?: string
  point?: string
  currentValue?: string
  threshold?: string
  triggeredAt: string
  message: string
}

export interface SystemNotificationConfig {
  retentionDays: number
  maxNotifications: number
  soundEnabled: boolean
  desktopEnabled: boolean
  autoReadMinutes: number
  quietHoursEnabled: boolean
  quietHoursStart: string
  quietHoursEnd: string
  notifyLevels: Array<'critical' | 'warning' | 'info'>
}

export interface NotificationChannel {
  id: string
  name: string
  type: 'email' | 'sms' | 'webhook' | 'system'
  enabled: boolean
  config: Record<string, any>
}

function mapAlertFromApi(a: AlertResponse): Alert {
  return {
    id: a.id,
    ruleId: a.rule_id,
    ruleName: a.rule_name || a.title,
    level: (['critical', 'warning', 'info'].includes(a.level) ? a.level : 'info') as Alert['level'],
    status: (['new', 'acknowledged', 'resolved', 'ignored'].includes(a.status) ? a.status : 'new') as Alert['status'],
    asset: a.asset || undefined,
    point: a.point_name || undefined,
    currentValue: a.current_value || undefined,
    threshold: a.threshold || undefined,
    triggeredAt: a.triggered_at_str || (a.triggered_at ? new Date(a.triggered_at * 1000).toLocaleString() : ''),
    message: a.message || a.title,
  }
}

export const useAlertStore = defineStore('alerts', () => {
  const alerts = ref<Alert[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const channels = ref<NotificationChannel[]>([
    {
      id: 'channel-001',
      name: '系统通知',
      type: 'system',
      enabled: true,
      config: {
        retentionDays: 30,
        maxNotifications: 1000,
        soundEnabled: true,
        desktopEnabled: true,
        autoReadMinutes: 0,
        quietHoursEnabled: false,
        quietHoursStart: '22:00',
        quietHoursEnd: '08:00',
        notifyLevels: ['critical', 'warning', 'info']
      } as SystemNotificationConfig
    },
    {
      id: 'channel-002',
      name: '邮件通知',
      type: 'email',
      enabled: true,
      config: {
        smtpHost: 'smtp.example.com',
        smtpPort: 587,
        fromAddress: 'alert@xagent.com'
      }
    },
    {
      id: 'channel-003',
      name: 'Webhook通知',
      type: 'webhook',
      enabled: false,
      config: {
        url: 'https://hooks.example.com/alert',
        method: 'POST'
      }
    }
  ])

  const pendingAlerts = computed(() =>
    alerts.value.filter(a => a.status === 'new').length
  )

  const criticalAlerts = computed(() =>
    alerts.value.filter(a => a.level === 'critical' && a.status === 'new').length
  )

  async function fetchAlerts() {
    loading.value = true
    error.value = null
    try {
      const res = await ruleApi.listAlerts()
      alerts.value = res.alerts.map(mapAlertFromApi)
    } catch (e: any) {
      error.value = e.message || '获取告警记录失败'
      console.error('Failed to fetch alerts:', e)
    } finally {
      loading.value = false
    }
  }

  async function acknowledgeAlert(id: string) {
    try {
      await ruleApi.acknowledgeAlert(id)
      const alert = alerts.value.find(a => a.id === id)
      if (alert) {
        alert.status = 'acknowledged'
      }
    } catch (e: any) {
      console.error('Failed to acknowledge alert:', e)
      throw e
    }
  }

  async function resolveAlert(id: string) {
    try {
      await ruleApi.resolveAlert(id)
      const alert = alerts.value.find(a => a.id === id)
      if (alert) {
        alert.status = 'resolved'
      }
    } catch (e: any) {
      console.error('Failed to resolve alert:', e)
      throw e
    }
  }

  async function ignoreAlert(id: string) {
    try {
      await ruleApi.ignoreAlert(id)
      const alert = alerts.value.find(a => a.id === id)
      if (alert) {
        alert.status = 'ignored'
      }
    } catch (e: any) {
      console.error('Failed to ignore alert:', e)
      throw e
    }
  }

  async function clearResolvedAlerts() {
    try {
      await ruleApi.clearResolvedAlerts()
      alerts.value = alerts.value.filter(a => a.status !== 'resolved')
    } catch (e: any) {
      console.error('Failed to clear resolved alerts:', e)
      throw e
    }
  }

  const toggleChannel = (id: string) => {
    const channel = channels.value.find(c => c.id === id)
    if (channel) {
      channel.enabled = !channel.enabled
    }
  }

  const updateChannelConfig = (id: string, config: Record<string, any>) => {
    const channel = channels.value.find(c => c.id === id)
    if (channel) {
      channel.config = { ...channel.config, ...config }
    }
  }

  return {
    alerts,
    loading,
    error,
    channels,
    pendingAlerts,
    criticalAlerts,
    fetchAlerts,
    acknowledgeAlert,
    resolveAlert,
    ignoreAlert,
    clearResolvedAlerts,
    toggleChannel,
    updateChannelConfig
  }
}, {
  persist: {
    key: 'xagent-alerts-v1',
    storage: sessionStorage,
    paths: ['alerts']
  }
})
