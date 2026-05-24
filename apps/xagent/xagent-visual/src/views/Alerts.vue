<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useAlertStore, type SystemNotificationConfig } from '@/stores/alerts'
import { useUserStore } from '@/stores/users'
import { useResponsive } from '@/utils/useResponsive'
import { ElMessage, ElMessageBox } from 'element-plus'

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
  retentionDays: [{ required: true, message: '请输入保留天数', trigger: 'blur' }],
  maxNotifications: [{ required: true, message: '请输入最大通知数', trigger: 'blur' }],
  quietHoursStart: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  quietHoursEnd: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
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
  smtpHost: [{ required: true, message: '请输入SMTP服务器', trigger: 'blur' }],
  smtpPort: [{ required: true, message: '请输入SMTP端口', trigger: 'blur' }],
  fromAddress: [{ required: true, message: '请输入发件人地址', trigger: 'blur' }],
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
  url: [{ required: true, message: '请输入Webhook URL', trigger: 'blur' }],
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
    critical: '紧急',
    warning: '警告',
    info: '提示'
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
    new: '未处理',
    acknowledged: '已确认',
    resolved: '已解决',
    ignored: '已忽略'
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
    ElMessage.success('告警已确认')
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleResolve = async (id: string) => {
  try {
    await alertStore.resolveAlert(id)
    ElMessage.success('告警已解决')
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleIgnore = async (id: string) => {
  try {
    await alertStore.ignoreAlert(id)
    ElMessage.success('告警已忽略')
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleClearAll = () => {
  ElMessageBox.confirm(
    '确定要清除所有已解决的告警吗？',
    '清除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await alertStore.clearResolvedAlerts()
      ElMessage.success('已清除解决的告警')
    } catch {
      ElMessage.error('清除失败')
    }
  }).catch(() => {})
}

const handleToggleChannel = (id: string) => {
  alertStore.toggleChannel(id)
  const channel = alertStore.channels.find(c => c.id === id)
  if (channel) {
    ElMessage.success(channel.enabled ? '通道已启用' : '通道已禁用')
  }
}

const getChannelTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    email: '邮件',
    sms: '短信',
    webhook: 'Webhook',
    system: '系统通知'
  }
  return labels[type] || type
}

const getSystemNotifyLevelLabels = (levels: Array<'critical' | 'warning' | 'info'>) => {
  const map: Record<string, string> = { critical: '紧急', warning: '警告', info: '提示' }
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
    ElMessage.success('系统通知配置已保存')
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
    ElMessage.success('邮件通知配置已保存')
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
    ElMessage.success('Webhook 配置已保存')
    webhookConfigDialogVisible.value = false
  }
}

const handleTestChannel = (channelId: string) => {
  const channel = alertStore.channels.find(c => c.id === channelId)
  if (!channel) return

  if (!channel.enabled) {
    ElMessage.warning('请先启用该通知渠道')
    return
  }

  if (channel.type === 'system') {
    testSystemNotification()
  }
}

const testSystemNotification = () => {
  if (Notification.permission === 'denied') {
    ElMessage.warning('浏览器已禁止桌面通知，请在浏览器设置中允许通知权限')
    return
  }

  if (systemConfigForm.desktopEnabled && Notification.permission !== 'granted') {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        sendTestDesktopNotification()
      } else {
        ElMessage.warning('桌面通知权限被拒绝，将仅发送站内通知')
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
  new Notification('XAgent 系统通知测试', {
    body: '这是一条测试通知，如果您看到此消息，说明系统通知渠道工作正常。',
    icon: '/favicon.ico',
    tag: 'xagent-test-notification'
  })
  sendTestInAppNotification()
}

const sendTestInAppNotification = () => {
  ElMessage.success({
    message: '系统通知测试发送成功！通知渠道工作正常。',
    duration: 5000
  })
}
</script>

<template>
  <div class="alerts-page">
    <el-tabs v-model="activeTab" class="alerts-tabs">
      <el-tab-pane label="告警记录" name="alerts">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              placeholder="搜索告警..."
              :prefix-icon="Search"
              clearable
              class="toolbar-search"
            />
            <el-select 
              v-model="levelFilter" 
              placeholder="级别筛选" 
              clearable
              class="toolbar-filter"
            >
              <el-option label="全部" value="" />
              <el-option label="紧急" value="critical" />
              <el-option label="警告" value="warning" />
              <el-option label="提示" value="info" />
            </el-select>
            <el-select 
              v-model="statusFilter" 
              placeholder="状态筛选" 
              clearable
              class="toolbar-filter"
            >
              <el-option label="全部" value="" />
              <el-option label="未处理" value="new" />
              <el-option label="已确认" value="acknowledged" />
              <el-option label="已解决" value="resolved" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button @click="alertStore.fetchAlerts()" :loading="alertStore.loading">刷新</el-button>
            <el-button type="danger" @click="handleClearAll" v-if="userStore.hasPermission('alerts', 'delete')">清除已解决</el-button>
          </div>
        </div>
        
        <el-table :data="filteredAlerts" style="width: 100%" stripe v-loading="alertStore.loading">
          <template #empty>
            <div class="empty-alerts">
              <el-empty description="暂无告警记录" />
            </div>
          </template>
          <el-table-column label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="getLevelTag(row.level)" size="small">
                {{ getLevelLabel(row.level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="ruleName" label="告警规则" width="150" />
          <el-table-column prop="message" label="告警信息" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusTag(row.status)" size="small">
                {{ getStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="triggeredAt" label="触发时间" width="160" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button 
                v-if="row.status === 'new' && userStore.hasPermission('alerts', 'update')"
                type="primary" 
                size="small" 
                link
                @click="handleAcknowledge(row.id)"
              >
                确认
              </el-button>
              <el-button 
                v-if="(row.status !== 'resolved' && row.status !== 'ignored') && userStore.hasPermission('alerts', 'update')"
                type="success" 
                size="small" 
                link
                @click="handleResolve(row.id)"
              >
                解决
              </el-button>
              <el-button 
                v-if="row.status === 'new' && userStore.hasPermission('alerts', 'update')"
                type="warning" 
                size="small" 
                link
                @click="handleIgnore(row.id)"
              >
                忽略
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      
      <el-tab-pane label="通知渠道" name="channels">
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
                      <span class="label">保留天数:</span>
                      <span class="value">{{ channel.config.retentionDays }} 天</span>
                    </div>
                    <div class="config-item">
                      <span class="label">通知上限:</span>
                      <span class="value">{{ channel.config.maxNotifications }} 条</span>
                    </div>
                    <div class="config-item">
                      <span class="label">通知级别:</span>
                      <span class="value">{{ getSystemNotifyLevelLabels(channel.config.notifyLevels) }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">桌面通知:</span>
                      <span class="value">{{ channel.config.desktopEnabled ? '已开启' : '已关闭' }}</span>
                    </div>
                    <div class="config-item">
                      <span class="label">提示音:</span>
                      <span class="value">{{ channel.config.soundEnabled ? '已开启' : '已关闭' }}</span>
                    </div>
                    <div v-if="channel.config.quietHoursEnabled" class="config-item">
                      <span class="label">免打扰:</span>
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
                    配置
                  </el-button>
                  <el-button 
                    v-else-if="userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleConfigureChannel(channel.id)"
                  >
                    配置
                  </el-button>
                  <el-button 
                    v-if="channel.type === 'system' && userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleTestChannel(channel.id)"
                  >
                    测试
                  </el-button>
                  <el-button 
                    v-else-if="userStore.hasPermission('alerts', 'update')"
                    type="primary" 
                    link 
                    size="small"
                    @click="handleTestChannel(channel.id)"
                  >
                    测试
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
      title="系统通知配置"
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
        <el-divider content-position="left">基本设置</el-divider>

        <el-form-item label="通知保留天数" prop="retentionDays">
          <el-input-number
            v-model="systemConfigForm.retentionDays"
            :min="1"
            :max="365"
            controls-position="right"
          />
          <span class="form-item-hint">超过保留天数的通知将自动清除</span>
        </el-form-item>

        <el-form-item label="最大通知数" prop="maxNotifications">
          <el-input-number
            v-model="systemConfigForm.maxNotifications"
            :min="100"
            :max="10000"
            :step="100"
            controls-position="right"
          />
          <span class="form-item-hint">超出上限时自动清除最早的通知</span>
        </el-form-item>

        <el-form-item label="通知级别" prop="notifyLevels">
          <el-checkbox-group v-model="systemConfigForm.notifyLevels">
            <el-checkbox label="critical">紧急</el-checkbox>
            <el-checkbox label="warning">警告</el-checkbox>
            <el-checkbox label="info">提示</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-divider content-position="left">通知方式</el-divider>

        <el-form-item label="桌面通知">
          <el-switch v-model="systemConfigForm.desktopEnabled" />
          <span class="form-item-hint">通过浏览器推送桌面通知弹窗</span>
        </el-form-item>

        <el-form-item label="提示音">
          <el-switch v-model="systemConfigForm.soundEnabled" />
          <span class="form-item-hint">收到新通知时播放提示音</span>
        </el-form-item>

        <el-divider content-position="left">免打扰</el-divider>

        <el-form-item label="免打扰模式">
          <el-switch v-model="systemConfigForm.quietHoursEnabled" />
          <span class="form-item-hint">在设定时段内不发送桌面通知和提示音</span>
        </el-form-item>

        <template v-if="systemConfigForm.quietHoursEnabled">
          <el-form-item label="开始时间" prop="quietHoursStart">
            <el-time-select
              v-model="systemConfigForm.quietHoursStart"
              start="00:00"
              step="00:30"
              end="23:30"
              placeholder="选择开始时间"
            />
          </el-form-item>
          <el-form-item label="结束时间" prop="quietHoursEnd">
            <el-time-select
              v-model="systemConfigForm.quietHoursEnd"
              start="00:00"
              step="00:30"
              end="23:30"
              placeholder="选择结束时间"
            />
          </el-form-item>
        </template>

        <el-divider content-position="left">自动处理</el-divider>

        <el-form-item label="自动已读">
          <el-input-number
            v-model="systemConfigForm.autoReadMinutes"
            :min="0"
            :max="10080"
            controls-position="right"
          />
          <span class="form-item-hint">通知发出后自动标记为已读（分钟，0 为不自动已读）</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="systemConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSystemConfig" v-if="userStore.hasPermission('alerts', 'update')">保存配置</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="emailConfigDialogVisible"
      title="邮件通知配置"
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
        <el-divider content-position="left">SMTP 服务器</el-divider>

        <el-form-item label="服务器地址" prop="smtpHost">
          <el-input v-model="emailConfigForm.smtpHost" placeholder="smtp.example.com" />
        </el-form-item>

        <el-form-item label="端口" prop="smtpPort">
          <el-input-number v-model="emailConfigForm.smtpPort" :min="1" :max="65535" controls-position="right" />
        </el-form-item>

        <el-form-item label="启用 TLS">
          <el-switch v-model="emailConfigForm.useTls" />
        </el-form-item>

        <el-divider content-position="left">认证信息</el-divider>

        <el-form-item label="用户名">
          <el-input v-model="emailConfigForm.username" placeholder="user@example.com" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="emailConfigForm.password" type="password" show-password placeholder="********" />
        </el-form-item>

        <el-form-item label="发件人地址" prop="fromAddress">
          <el-input v-model="emailConfigForm.fromAddress" placeholder="noreply@example.com" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="emailConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveEmailConfig" v-if="userStore.hasPermission('alerts', 'update')">保存配置</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="webhookConfigDialogVisible"
      title="Webhook 配置"
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

        <el-form-item label="请求方法">
          <el-select v-model="webhookConfigForm.method" style="width: 200px">
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
          </el-select>
        </el-form-item>

        <el-form-item label="自定义请求头">
          <el-input
            v-model="webhookConfigForm.headers"
            type="textarea"
            :rows="3"
            placeholder='{"Content-Type": "application/json"}'
          />
        </el-form-item>

        <el-form-item label="签名密钥">
          <el-input v-model="webhookConfigForm.secret" type="password" show-password placeholder="用于验证请求来源" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="webhookConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveWebhookConfig" v-if="userStore.hasPermission('alerts', 'update')">保存配置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

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
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
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
  color: #2c3e50;
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
  background: #f0f2f5;
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
  color: #2c3e50;
  margin-bottom: 4px;
}

.channel-config {
  padding: 12px;
  background: #f8f9fa;
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
  color: #7f8c8d;
  min-width: 70px;
}

.config-item .value {
  color: #2c3e50;
}

.channel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.system-config-form .el-divider {
  margin: 20px 0 16px;
}

.system-config-form .el-divider__text {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.form-item-hint {
  display: block;
  font-size: 12px;
  color: #909399;
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
