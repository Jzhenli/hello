<template>
  <div class="alerts-page">
    <el-tabs v-model="activeTab" class="alerts-tabs">
      <el-tab-pane :label="$t('alerts.tabAlerts')" name="alerts">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              :placeholder="$t('alerts.searchPlaceholder')"
              :prefix-icon="Search"
              clearable
              class="toolbar-search"
            />
            <el-select 
              v-model="levelFilter" 
              :placeholder="$t('alerts.levelFilter')" 
              clearable
              class="toolbar-filter"
            >
              <el-option :label="$t('common.all')" value="" />
              <el-option :label="$t('alerts.levelCritical')" value="critical" />
              <el-option :label="$t('alerts.levelWarning')" value="warning" />
              <el-option :label="$t('alerts.levelInfo')" value="info" />
            </el-select>
            <el-select 
              v-model="statusFilter" 
              :placeholder="$t('alerts.statusFilter')" 
              clearable
              class="toolbar-filter"
            >
              <el-option :label="$t('common.all')" value="" />
              <el-option :label="$t('alerts.statusNew')" value="new" />
              <el-option :label="$t('alerts.statusAcknowledged')" value="acknowledged" />
              <el-option :label="$t('alerts.statusResolved')" value="resolved" />
              <el-option :label="$t('alerts.statusIgnored')" value="ignored" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="alertStore.fetchAlerts()" :loading="alertStore.loading">{{ $t('common.refresh') }}</el-button>
            <el-button type="danger" @click="handleClearAll" v-if="userStore.hasPermission('alerts', 'delete')">{{ $t('alerts.clearResolved') }}</el-button>
          </div>
        </div>
        
        <el-table :data="filteredAlerts" style="width: 100%" stripe v-loading="alertStore.loading">
          <template #empty>
            <div class="empty-alerts">
              <el-empty :description="$t('alerts.noAlerts')" />
            </div>
          </template>
          <el-table-column :label="$t('alerts.level')" width="100">
            <template #default="{ row }">
              <el-tag :type="getLevelTag(row.level)" size="small">
                {{ getLevelLabel(row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="ruleName" :label="$t('alerts.alertRule')" width="150" />
          <el-table-column prop="message" :label="$t('alerts.alertMessage')" show-overflow-tooltip />
          <el-table-column :label="$t('alerts.status')" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusTag(row.status)" size="small">
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="triggeredAt" :label="$t('alerts.triggeredAt')" width="160" />
          <el-table-column :label="$t('common.actions')" width="200" fixed="right">
            <template #default="{ row }">
              <el-button 
                v-if="row.status === 'new' && userStore.hasPermission('alerts', 'update')"
                type="primary" 
                size="small" 
                link
                @click="handleAcknowledge(row.id)"
              >
                {{ $t('alerts.acknowledge') }}
              </el-button>
              <el-button 
                v-if="(row.status !== 'resolved' && row.status !== 'ignored') && userStore.hasPermission('alerts', 'update')"
                type="success" 
                size="small" 
                link
                @click="handleResolve(row.id)"
              >
                {{ $t('alerts.resolve') }}
              </el-button>
              <el-button 
                v-if="row.status === 'new' && userStore.hasPermission('alerts', 'update')"
                type="warning" 
                size="small" 
                link
                @click="handleIgnore(row.id)"
              >
                {{ $t('alerts.ignore') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      
      <el-tab-pane :label="$t('alerts.tabChannels')" name="channels">
        <div class="channels-section">
          <el-row :gutter="20">
            <el-col 
              v-for="channel in alertStore.channels" 
              :key="channel.id" 
              :span="channelColSpan"
            >
              <el-card class="channel-card" shadow="hover">
                <div class="channel-header">
                  <div class="channel-icon">
                    <span v-if="channel.type === 'email'">📧</span>
                    <span v-else-if="channel.type === 'sms'">📱</span>
                    <span v-else-if="channel.type === 'webhook'">🔗</span>
                    <span v-else>🔔</span>
                  </div>
                  <div class="channel-info">
                    <div class="channel-name">{{ channel.name }}</div>
                    <el-tag size="small">{{ getChannelTypeLabel(channel.type) }}</el-tag>
                  </div>
                  <el-switch 
                    v-if="userStore.hasPermission('alerts', 'update')"
                    :model-value="channel.enabled"
                    @change="handleToggleChannel(channel.id)"
                  />
                </div>
                <div class="channel-config">
                  <div v-if="channel.type === 'email'" class="config-item">
                    <span class="label">SMTP:</span>
                    <span class="value">{{ channel.config.smtpHost }}:{{ channel.config.smtpPort }}</span>
                  </div>
                  <div v-if="channel.type === 'webhook'" class="config-item">
                    <span class="label">URL:</span>
                    <span class="value">{{ channel.config.url }}</span>
                  </div>
                  <template v-if="channel.type === 'system'">
                    <div class="config-item">
                      <span class="label">{{ $t('alerts.retentionDays') }}:</span>
                      <span class="value">{{ channel.config.retentionDays }} {{ $t('alerts.days') }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">{{ $t('alerts.notificationLimit') }}:</span>
                      <span class="value">{{ channel.config.maxNotifications }} {{ $t('alerts.items') }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">{{ $t('alerts.notificationLevels') }}:</span>
                      <span class="value">{{ getSystemNotifyLevelLabels(channel.config.notifyLevels) }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">{{ $t('alerts.desktopNotification') }}:</span>
                      <span class="value">{{ channel.config.desktopEnabled ? $t('alerts.enabled') : $t('alerts.disabled') }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">{{ $t('alerts.sound') }}:</span>
                      <span class="value">{{ channel.config.soundEnabled ? $t('alerts.enabled') : $t('alerts.disabled') }}</span>
                    </div>
                    <div v-if="channel.config.quietHoursEnabled" class="config-item">
                      <span class="label">{{ $t('alerts.doNotDisturb') }}:</span>
                      <span class="value">{{ channel.config.quietHoursStart }} - {{ channel.config.quietHoursEnd }}</span>
                    </div>
                  </template>
                </div>
                <div class="channel-footer">
                  <el-button 
                    v-if="channel.type === 'system' && userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleConfigureChannel(channel.id)"
                  >
                    {{ $t('alerts.configure') }}
                  </el-button>
                  <el-button 
                    v-else-if="userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleConfigureChannel(channel.id)"
                  >
                    {{ $t('alerts.configure') }}
                  </el-button>
                  <el-button 
                    v-if="channel.type === 'system' && userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleTestChannel(channel.id)"
                  >
                    {{ $t('common.test') }}
                  </el-button>
                  <el-button 
                    v-else-if="userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleTestChannel(channel.id)"
                  >
                    {{ $t('common.test') }}
                  </el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="systemConfigDialogVisible"
      :title="$t('alerts.systemConfigTitle')"
      width="min(560px, 92vw)"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="systemConfigFormRef"
        :model="systemConfigForm"
        :rules="systemConfigRules"
        label-width="110px"
        class="system-config-form"
      >
        <el-divider content-position="left">{{ $t('alerts.basicSettings') }}</el-divider>

        <el-form-item :label="$t('alerts.retentionDaysLabel')" prop="retentionDays">
          <el-input-number
            v-model="systemConfigForm.retentionDays"
            :min="1"
            :max="365"
            controls-position="right"
          />
          <span class="form-item-hint">{{ $t('alerts.retentionDaysHint') }}</span>
        </el-form-item>

        <el-form-item :label="$t('alerts.maxNotificationsLabel')" prop="maxNotifications">
          <el-input-number
            v-model="systemConfigForm.maxNotifications"
            :min="100"
            :max="10000"
            :step="100"
            controls-position="right"
          />
          <span class="form-item-hint">{{ $t('alerts.maxNotificationsHint') }}</span>
        </el-form-item>

        <el-form-item :label="$t('alerts.notificationLevelsLabel')" prop="notifyLevels">
          <el-checkbox-group v-model="systemConfigForm.notifyLevels">
            <el-checkbox label="critical">{{ $t('alerts.levelCritical') }}</el-checkbox>
            <el-checkbox label="warning">{{ $t('alerts.levelWarning') }}</el-checkbox>
            <el-checkbox label="info">{{ $t('alerts.levelInfo') }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-divider content-position="left">{{ $t('alerts.notificationMethods') }}</el-divider>

        <el-form-item :label="$t('alerts.desktopNotificationLabel')">
          <el-switch v-model="systemConfigForm.desktopEnabled" />
          <span class="form-item-hint">{{ $t('alerts.desktopNotificationHint') }}</span>
        </el-form-item>

        <el-form-item :label="$t('alerts.soundLabel')">
          <el-switch v-model="systemConfigForm.soundEnabled" />
          <span class="form-item-hint">{{ $t('alerts.soundHint') }}</span>
        </el-form-item>

        <el-divider content-position="left">{{ $t('alerts.doNotDisturb') }}</el-divider>

        <el-form-item :label="$t('alerts.doNotDisturbLabel')">
          <el-switch v-model="systemConfigForm.quietHoursEnabled" />
          <span class="form-item-hint">{{ $t('alerts.doNotDisturbHint') }}</span>
        </el-form-item>

        <template v-if="systemConfigForm.quietHoursEnabled">
          <el-form-item :label="$t('alerts.startTimeLabel')" prop="quietHoursStart">
            <el-time-select
              v-model="systemConfigForm.quietHoursStart"
              start="00:00"
              step="00:30"
              end="23:30"
              :placeholder="$t('alerts.selectStartTime')"
            />
          </el-form-item>
          <el-form-item :label="$t('alerts.endTimeLabel')" prop="quietHoursEnd">
            <el-time-select
              v-model="systemConfigForm.quietHoursEnd"
              start="00:00"
              step="00:30"
              end="23:30"
              :placeholder="$t('alerts.selectEndTime')"
            />
          </el-form-item>
        </template>

        <el-divider content-position="left">{{ $t('alerts.autoProcess') }}</el-divider>

        <el-form-item :label="$t('alerts.autoReadLabel')">
          <el-input-number
            v-model="systemConfigForm.autoReadMinutes"
            :min="0"
            :max="10080"
            controls-position="right"
          />
          <span class="form-item-hint">{{ $t('alerts.autoReadHint') }}</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="systemConfigDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveSystemConfig" v-if="userStore.hasPermission('alerts', 'update')">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="emailConfigDialogVisible"
      :title="$t('alerts.emailConfigTitle')"
      width="min(520px, 92vw)"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="emailConfigFormRef"
        :model="emailConfigForm"
        :rules="emailConfigRules"
        label-width="110px"
        class="system-config-form"
      >
        <el-divider content-position="left">{{ $t('alerts.smtpServer') }}</el-divider>

        <el-form-item :label="$t('alerts.serverAddress')" prop="smtpHost">
          <el-input v-model="emailConfigForm.smtpHost" placeholder="smtp.example.com" />
        </el-form-item>

        <el-form-item :label="$t('alerts.port')" prop="smtpPort">
          <el-input-number v-model="emailConfigForm.smtpPort" :min="1" :max="65535" controls-position="right" />
        </el-form-item>

        <el-form-item :label="$t('alerts.enableTls')">
          <el-switch v-model="emailConfigForm.useTls" />
        </el-form-item>

        <el-divider content-position="left">{{ $t('alerts.authInfo') }}</el-divider>

        <el-form-item :label="$t('alerts.username')">
          <el-input v-model="emailConfigForm.username" placeholder="user@example.com" />
        </el-form-item>

        <el-form-item :label="$t('alerts.password')">
          <el-input v-model="emailConfigForm.password" type="password" show-password placeholder="********" />
        </el-form-item>

        <el-form-item :label="$t('alerts.fromAddressLabel')" prop="fromAddress">
          <el-input v-model="emailConfigForm.fromAddress" placeholder="noreply@example.com" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="emailConfigDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveEmailConfig" v-if="userStore.hasPermission('alerts', 'update')">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="webhookConfigDialogVisible"
      :title="$t('alerts.webhookConfigTitle')"
      width="min(520px, 92vw)"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="webhookConfigFormRef"
        :model="webhookConfigForm"
        :rules="webhookConfigRules"
        label-width="110px"
        class="system-config-form"
      >
        <el-form-item label="URL" prop="url">
          <el-input v-model="webhookConfigForm.url" placeholder="https://hooks.example.com/alert" />
        </el-form-item>

        <el-form-item :label="$t('alerts.requestMethod')">
          <el-select v-model="webhookConfigForm.method" style="width: 200px">
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
          </el-select>
        </el-form-item>

        <el-form-item :label="$t('alerts.customHeaders')">
          <el-input
            v-model="webhookConfigForm.headers"
            type="textarea"
            :rows="3"
            placeholder='{"Content-Type": "application/json"}'
          />
        </el-form-item>

        <el-form-item :label="$t('alerts.signatureKey')">
          <el-input v-model="webhookConfigForm.secret" type="password" show-password :placeholder="$t('alerts.signatureKeyHint')" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="webhookConfigDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveWebhookConfig" v-if="userStore.hasPermission('alerts', 'update')">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAlertStore, type SystemNotificationConfig } from '@/stores/alerts'
import { useUserStore } from '@/stores/users'
import { useResponsive } from '@/utils/useResponsive'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t } = useI18n()

const alertStore = useAlertStore()
const userStore = useUserStore()
const { isTablet, isMobile } = useResponsive()

onMounted(() => {
  alertStore.fetchAlerts()
})

const channelColSpan = computed(() => {
  if (isMobile.value) return 24
  if (isTablet.value) return 12
  return 8
})

const activeTab = ref('alerts')
const searchQuery = ref('')
const levelFilter = ref('')
const statusFilter = ref('')

const systemConfigDialogVisible = ref(false)
const systemConfigForm = reactive<SystemNotificationConfig>({
  retentionDays: 30,
  maxNotifications: 1000,
  soundEnabled: true,
  desktopEnabled: true,
  autoReadMinutes: 0,
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '08:00',
  notifyLevels: ['critical', 'warning', 'info']
})

const systemConfigRules = {
  retentionDays: [{ required: true, message: t('alerts.retentionDaysRequired'), trigger: 'blur' }],
  maxNotifications: [{ required: true, message: t('alerts.maxNotificationsRequired'), trigger: 'blur' }],
  quietHoursStart: [{ required: true, message: t('alerts.startTimeRequired'), trigger: 'change' }],
  quietHoursEnd: [{ required: true, message: t('alerts.endTimeRequired'), trigger: 'change' }]
}

const systemConfigFormRef = ref()

const emailConfigDialogVisible = ref(false)
const emailConfigForm = reactive({
  smtpHost: '',
  smtpPort: 587,
  username: '',
  password: '',
  fromAddress: '',
  useTls: true,
})
const emailConfigRules = {
  smtpHost: [{ required: true, message: t('alerts.smtpHostRequired'), trigger: 'blur' }],
  smtpPort: [{ required: true, message: t('alerts.smtpPortRequired'), trigger: 'blur' }],
  fromAddress: [{ required: true, message: t('alerts.fromAddressRequired'), trigger: 'blur' }],
}
const emailConfigFormRef = ref()

const webhookConfigDialogVisible = ref(false)
const webhookConfigForm = reactive({
  url: '',
  method: 'POST',
  headers: '',
  secret: '',
})
const webhookConfigRules = {
  url: [{ required: true, message: t('alerts.webhookUrlRequired'), trigger: 'blur' }],
}
const webhookConfigFormRef = ref()

const filteredAlerts = computed(() => {
  let alerts = [...alertStore.alerts]
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    alerts = alerts.filter(a => 
      a.ruleName.toLowerCase().includes(query) || 
      a.message.toLowerCase().includes(query)
    )
  }
  
  if (levelFilter.value) {
    alerts = alerts.filter(a => a.level === levelFilter.value)
  }
  
  if (statusFilter.value) {
    alerts = alerts.filter(a => a.status === statusFilter.value)
  }
  
  return alerts
})

const getLevelLabel = (level: string) => {
  const labels: Record<string, string> = {
    critical: t('alerts.levelCritical'),
    warning: t('alerts.levelWarning'),
    info: t('alerts.levelInfo')
  }
  return labels[level] || level
}

const getLevelTag = (level: string) => {
  const tags: Record<string, string> = {
    critical: 'danger',
    warning: 'warning',
    info: 'info'
  }
  return tags[level] || 'info'
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    new: t('alerts.statusNew'),
    acknowledged: t('alerts.statusAcknowledged'),
    resolved: t('alerts.statusResolved'),
    ignored: t('alerts.statusIgnored')
  }
  return labels[status] || status
}

const getStatusTag = (status: string) => {
  const tags: Record<string, string> = {
    new: 'danger',
    acknowledged: 'warning',
    resolved: 'success',
    ignored: 'info'
  }
  return tags[status] || 'info'
}

const handleAcknowledge = async (id: string) => {
  try {
    await alertStore.acknowledgeAlert(id)
    ElMessage.success(t('alerts.acknowledgeSuccess'))
  } catch {
    ElMessage.error(t('common.operationFailed'))
  }
}

const handleResolve = async (id: string) => {
  try {
    await alertStore.resolveAlert(id)
    ElMessage.success(t('alerts.resolveSuccess'))
  } catch {
    ElMessage.error(t('common.operationFailed'))
  }
}

const handleIgnore = async (id: string) => {
  try {
    await alertStore.ignoreAlert(id)
    ElMessage.success(t('alerts.ignoreSuccess'))
  } catch {
    ElMessage.error(t('common.operationFailed'))
  }
}

const handleClearAll = () => {
  ElMessageBox.confirm(
    t('alerts.clearAllConfirm'),
    t('alerts.clearConfirmTitle'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      await alertStore.clearResolvedAlerts()
      ElMessage.success(t('alerts.clearSuccess'))
    } catch {
      ElMessage.error(t('alerts.clearFailed'))
    }
  }).catch(() => {})
}

const handleToggleChannel = (id: string) => {
  alertStore.toggleChannel(id)
  const channel = alertStore.channels.find(c => c.id === id)
  if (channel) {
    ElMessage.success(channel.enabled ? t('alerts.channelEnabled') : t('alerts.channelDisabled'))
  }
}

const getChannelTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    email: t('alerts.channelEmail'),
    sms: t('alerts.channelSms'),
    webhook: 'Webhook',
    system: t('alerts.channelSystem')
  }
  return labels[type] || type
}

const getSystemNotifyLevelLabels = (levels: Array<'critical' | 'warning' | 'info'>) => {
  const map: Record<string, string> = { critical: t('alerts.levelCritical'), warning: t('alerts.levelWarning'), info: t('alerts.levelInfo') }
  return levels.map(l => map[l]).join('、')
}

const handleConfigureChannel = (channelId: string) => {
  const channel = alertStore.channels.find(c => c.id === channelId)
  if (!channel) return

  if (channel.type === 'system') {
    Object.assign(systemConfigForm, {
      retentionDays: channel.config.retentionDays ?? 30,
      maxNotifications: channel.config.maxNotifications ?? 1000,
      soundEnabled: channel.config.soundEnabled ?? true,
      desktopEnabled: channel.config.desktopEnabled ?? true,
      autoReadMinutes: channel.config.autoReadMinutes ?? 0,
      quietHoursEnabled: channel.config.quietHoursEnabled ?? false,
      quietHoursStart: channel.config.quietHoursStart ?? '22:00',
      quietHoursEnd: channel.config.quietHoursEnd ?? '08:00',
      notifyLevels: [...(channel.config.notifyLevels ?? ['critical', 'warning', 'info'])]
    })
    systemConfigDialogVisible.value = true
  } else if (channel.type === 'email') {
    Object.assign(emailConfigForm, {
      smtpHost: channel.config.smtpHost ?? '',
      smtpPort: channel.config.smtpPort ?? 587,
      username: channel.config.username ?? '',
      password: channel.config.password ?? '',
      fromAddress: channel.config.fromAddress ?? '',
      useTls: channel.config.useTls ?? true,
    })
    emailConfigDialogVisible.value = true
  } else if (channel.type === 'webhook') {
    Object.assign(webhookConfigForm, {
      url: channel.config.url ?? '',
      method: channel.config.method ?? 'POST',
      headers: channel.config.headers ?? '',
      secret: channel.config.secret ?? '',
    })
    webhookConfigDialogVisible.value = true
  }
}

const handleSaveSystemConfig = async () => {
  if (!systemConfigFormRef.value) return
  try {
    await systemConfigFormRef.value.validate()
  } catch {
    return
  }

  const systemChannel = alertStore.channels.find(c => c.type === 'system')
  if (systemChannel) {
    alertStore.updateChannelConfig(systemChannel.id, { ...systemConfigForm })
    ElMessage.success(t('alerts.systemConfigSaved'))
    systemConfigDialogVisible.value = false
  }
}

const handleSaveEmailConfig = async () => {
  if (!emailConfigFormRef.value) return
  try {
    await emailConfigFormRef.value.validate()
  } catch {
    return
  }

  const emailChannel = alertStore.channels.find(c => c.type === 'email')
  if (emailChannel) {
    alertStore.updateChannelConfig(emailChannel.id, { ...emailConfigForm })
    ElMessage.success(t('alerts.emailConfigSaved'))
    emailConfigDialogVisible.value = false
  }
}

const handleSaveWebhookConfig = async () => {
  if (!webhookConfigFormRef.value) return
  try {
    await webhookConfigFormRef.value.validate()
  } catch {
    return
  }

  const webhookChannel = alertStore.channels.find(c => c.type === 'webhook')
  if (webhookChannel) {
    alertStore.updateChannelConfig(webhookChannel.id, { ...webhookConfigForm })
    ElMessage.success(t('alerts.webhookConfigSaved'))
    webhookConfigDialogVisible.value = false
  }
}

const handleTestChannel = (channelId: string) => {
  const channel = alertStore.channels.find(c => c.id === channelId)
  if (!channel) return

  if (!channel.enabled) {
    ElMessage.warning(t('alerts.enableChannelFirst'))
    return
  }

  if (channel.type === 'system') {
    testSystemNotification()
  }
}

const testSystemNotification = () => {
  if (Notification.permission === 'denied') {
    ElMessage.warning(t('alerts.notificationDenied'))
    return
  }

  if (systemConfigForm.desktopEnabled && Notification.permission !== 'granted') {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        sendTestDesktopNotification()
      } else {
        ElMessage.warning(t('alerts.desktopNotificationDenied'))
        sendTestInAppNotification()
      }
    })
  } else if (systemConfigForm.desktopEnabled && Notification.permission === 'granted') {
    sendTestDesktopNotification()
  } else {
    sendTestInAppNotification()
  }
}

const sendTestDesktopNotification = () => {
  new Notification(t('alerts.testNotificationTitle'), {
    body: t('alerts.testNotificationBody'),
    icon: '/favicon.ico',
    tag: 'xagent-test-notification'
  })
  sendTestInAppNotification()
}

const sendTestInAppNotification = () => {
  ElMessage.success({
    message: t('alerts.testNotificationSuccess'),
    duration: 5000
  })
}
</script>

<script lang="ts">
import { Search, Plus } from '@element-plus/icons-vue'
export default {
  components: { Search, Plus }
}
</script>

<style scoped>
.alerts-page {
  padding: 0;
}

.alerts-tabs {
  background: var(--bg-container);
  border-radius: 8px;
  padding: 16px;
  box-shadow: var(--shadow-light);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-search {
  width: 250px;
}

.toolbar-filter {
  width: 120px;
}

.channels-section {
  padding: 16px 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

.channel-card {
  margin-bottom: 16px;
  height: 100%;
}

.channel-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.channel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.channel-icon {
  width: 40px;
  height: 40px;
  background: var(--bg-hover);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.channel-info {
  flex: 1;
}

.channel-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.channel-config {
  padding: 12px;
  background: var(--bg-hover);
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.config-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.config-item .label {
  color: var(--text-secondary);
  min-width: 70px;
}

.config-item .value {
  color: var(--text-primary);
}

.channel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-base);
}

.system-config-form .el-divider {
  margin: 20px 0 16px;
}

.system-config-form .el-divider__text {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.form-item-hint {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
  margin-top: 4px;
}

.system-config-form .el-checkbox-group {
  display: flex;
  gap: 16px;
}

.system-config-form .el-input-number {
  width: 160px;
}

.system-config-form .el-time-select {
  width: 160px;
}

@media (max-width: 1024px) {
  .toolbar-search {
    width: 200px;
  }

  .toolbar-filter {
    width: 110px;
  }

  .alerts-tabs {
    padding: 12px;
  }
}

@media (max-width: 768px) {
  .toolbar-search {
    width: 100%;
  }

  .toolbar-filter {
    width: 100%;
  }

  .alerts-tabs {
    padding: 8px;
  }
}
</style>
