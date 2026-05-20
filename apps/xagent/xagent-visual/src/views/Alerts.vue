<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAlertStore } from '@/stores/alerts'
import { 
  Bell,
  Check,
  Close,
  Delete
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const alertStore = useAlertStore()

const activeTab = ref('alerts')
const searchQuery = ref('')
const levelFilter = ref('')
const statusFilter = ref('')

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

const handleAcknowledge = (id: string) => {
  alertStore.acknowledgeAlert(id)
  ElMessage.success('告警已确认')
}

const handleResolve = (id: string) => {
  alertStore.resolveAlert(id)
  ElMessage.success('告警已解决')
}

const handleIgnore = (id: string) => {
  alertStore.ignoreAlert(id)
  ElMessage.success('告警已忽略')
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
  ).then(() => {
    alertStore.alerts = alertStore.alerts.filter(a => a.status !== 'resolved')
    ElMessage.success('已清除解决的告警')
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
</script>

<template>
  <div class="alerts-page">
    <div class="page-header">
      <h2>告警配置</h2>
    </div>
    
    <el-tabs v-model="activeTab" class="alerts-tabs">
      <el-tab-pane label="告警记录" name="alerts">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input
              v-model="searchQuery"
              placeholder="搜索告警..."
              :prefix-icon="Search"
              clearable
              style="width: 250px"
            />
            <el-select 
              v-model="levelFilter" 
              placeholder="级别筛选" 
              clearable
              style="width: 120px"
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
              style="width: 120px"
            >
              <el-option label="全部" value="" />
              <el-option label="未处理" value="new" />
              <el-option label="已确认" value="acknowledged" />
              <el-option label="已解决" value="resolved" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button type="danger" @click="handleClearAll">清除已解决</el-button>
          </div>
        </div>
        
        <el-table :data="filteredAlerts" style="width: 100%" stripe>
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
                v-if="row.status === 'new'"
                type="primary" 
                size="small" 
                link
                @click="handleAcknowledge(row.id)"
              >
                确认
              </el-button>
              <el-button 
                v-if="row.status !== 'resolved' && row.status !== 'ignored'"
                type="success" 
                size="small" 
                link
                @click="handleResolve(row.id)"
              >
                解决
              </el-button>
              <el-button 
                v-if="row.status === 'new'"
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
          <div class="section-header">
            <h3>通知渠道配置</h3>
            <el-button type="primary" :icon="Plus">添加渠道</el-button>
          </div>
          
          <el-row :gutter="20">
            <el-col 
              v-for="channel in alertStore.channels" 
              :key="channel.id" 
              :span="8"
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
                    v-model="channel.enabled"
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
                  <div v-if="channel.type === 'system'" class="config-item">
                    <span class="label">保留天数:</span>
                    <span class="value">{{ channel.config.retentionDays }} 天</span>
                  </div>
                </div>
                <div class="channel-footer">
                  <el-button type="primary" link size="small">配置</el-button>
                  <el-button type="primary" link size="small">测试</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
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

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #2c3e50;
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
}

.config-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.config-item .label {
  color: #7f8c8d;
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
</style>
