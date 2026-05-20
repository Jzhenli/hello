import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

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

export interface NotificationChannel {
  id: string
  name: string
  type: 'email' | 'sms' | 'webhook' | 'system'
  enabled: boolean
  config: Record<string, any>
}

export const useAlertStore = defineStore('alerts', () => {
  const alerts = ref<Alert[]>([
    {
      id: 'alert-001',
      ruleId: 'alert-rule-001',
      ruleName: '温度超限告警',
      level: 'critical',
      status: 'new',
      asset: 'KNX-01',
      point: 'temperature_1',
      currentValue: '38°C',
      threshold: '35°C',
      triggeredAt: '2026-04-27 10:23:45',
      message: '温度超限告警：KNX-01/temperature_1 = 38°C (上限: 35°C)'
    },
    {
      id: 'alert-002',
      ruleId: 'alert-rule-002',
      ruleName: '设备离线告警',
      level: 'warning',
      status: 'new',
      asset: 'BACNET-01',
      triggeredAt: '2026-04-27 10:15:22',
      message: '设备离线告警：BACNET-01 设备连接失败'
    },
    {
      id: 'alert-003',
      ruleId: 'alert-rule-003',
      ruleName: '湿度超限告警',
      level: 'info',
      status: 'acknowledged',
      asset: 'KNX-02',
      point: 'humidity_1',
      currentValue: '85%',
      threshold: '80%',
      triggeredAt: '2026-04-27 09:45:30',
      message: '湿度超限告警：KNX-02/humidity_1 = 85% (上限: 80%)'
    }
  ])

  const channels = ref<NotificationChannel[]>([
    {
      id: 'channel-001',
      name: '系统通知',
      type: 'system',
      enabled: true,
      config: { retentionDays: 30, maxNotifications: 1000 }
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

  const acknowledgeAlert = (id: string) => {
    const alert = alerts.value.find(a => a.id === id)
    if (alert) {
      alert.status = 'acknowledged'
    }
  }

  const resolveAlert = (id: string) => {
    const alert = alerts.value.find(a => a.id === id)
    if (alert) {
      alert.status = 'resolved'
    }
  }

  const ignoreAlert = (id: string) => {
    const alert = alerts.value.find(a => a.id === id)
    if (alert) {
      alert.status = 'ignored'
    }
  }

  const toggleChannel = (id: string) => {
    const channel = channels.value.find(c => c.id === id)
    if (channel) {
      channel.enabled = !channel.enabled
    }
  }

  return {
    alerts,
    channels,
    pendingAlerts,
    criticalAlerts,
    acknowledgeAlert,
    resolveAlert,
    ignoreAlert,
    toggleChannel
  }
})
