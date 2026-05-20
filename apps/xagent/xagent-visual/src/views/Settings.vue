<script setup lang="ts">
import { ref } from 'vue'
import { 
  Setting,
  Bell,
  Document,
  Refresh,
  User
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const activeMenu = ref('general')

const systemConfig = ref({
  logLevel: 'info',
  dataRetention: 30,
  maxConnections: 100,
  timeout: 30
})

const handleSave = () => {
  ElMessage.success('配置已保存')
}

const handleTestEmail = () => {
  ElMessage.success('测试邮件已发送')
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>
    
    <div class="settings-container">
      <div class="settings-sidebar">
        <el-menu :default-active="activeMenu" @select="(key: string) => activeMenu = key">
          <el-menu-item index="general">
            <el-icon><Setting /></el-icon>
            <span>系统配置</span>
          </el-menu-item>
          <el-menu-item index="notifications">
            <el-icon><Bell /></el-icon>
            <span>通知设置</span>
          </el-menu-item>
          <el-menu-item index="logs">
            <el-icon><Document /></el-icon>
            <span>日志查看</span>
          </el-menu-item>
          <el-menu-item index="backup">
            <el-icon><Refresh /></el-icon>
            <span>备份恢复</span>
          </el-menu-item>
          <el-menu-item index="users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
        </el-menu>
      </div>
      
      <div class="settings-content">
        <div v-if="activeMenu === 'general'" class="settings-section">
          <h3>系统配置</h3>
          <el-form label-width="120px" class="settings-form">
            <el-form-item label="日志级别">
              <el-select v-model="systemConfig.logLevel" style="width: 200px">
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
              </el-select>
            </el-form-item>
            <el-form-item label="数据保留天数">
              <el-input-number v-model="systemConfig.dataRetention" :min="1" :max="365" />
            </el-form-item>
            <el-form-item label="最大连接数">
              <el-input-number v-model="systemConfig.maxConnections" :min="1" :max="1000" />
            </el-form-item>
            <el-form-item label="超时时间(秒)">
              <el-input-number v-model="systemConfig.timeout" :min="1" :max="300" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave">保存配置</el-button>
            </el-form-item>
          </el-form>
        </div>
        
        <div v-if="activeMenu === 'notifications'" class="settings-section">
          <h3>通知设置</h3>
          <el-form label-width="120px" class="settings-form">
            <el-divider content-position="left">邮件通知</el-divider>
            <el-form-item label="SMTP服务器">
              <el-input placeholder="smtp.example.com" style="width: 300px" />
            </el-form-item>
            <el-form-item label="SMTP端口">
              <el-input-number :min="1" :max="65535" :value="587" />
            </el-form-item>
            <el-form-item label="用户名">
              <el-input placeholder="user@example.com" style="width: 300px" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input type="password" placeholder="********" style="width: 300px" />
            </el-form-item>
            <el-form-item label="发件人地址">
              <el-input placeholder="noreply@example.com" style="width: 300px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleTestEmail">发送测试邮件</el-button>
            </el-form-item>
            
            <el-divider content-position="left">短信通知</el-divider>
            <el-form-item label="服务商">
              <el-select placeholder="请选择" style="width: 200px">
                <el-option label="阿里云" value="aliyun" />
                <el-option label="腾讯云" value="tencent" />
              </el-select>
            </el-form-item>
            <el-form-item label="AccessKey ID">
              <el-input placeholder="请输入AccessKey ID" style="width: 300px" />
            </el-form-item>
            <el-form-item label="AccessKey Secret">
              <el-input type="password" placeholder="请输入AccessKey Secret" style="width: 300px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary">保存配置</el-button>
            </el-form-item>
          </el-form>
        </div>
        
        <div v-if="activeMenu === 'logs'" class="settings-section">
          <h3>日志查看</h3>
          <div class="log-viewer">
            <div class="log-toolbar">
              <el-select placeholder="日志级别" style="width: 120px">
                <el-option label="全部" value="" />
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
              </el-select>
              <el-button type="primary">刷新</el-button>
              <el-button>下载日志</el-button>
            </div>
            <div class="log-content">
              <div class="log-line info">
                <span class="log-time">2026-04-27 10:23:45</span>
                <span class="log-level">INFO</span>
                <span class="log-message">[KNX-01] 数据采集完成，共128个点位</span>
              </div>
              <div class="log-line info">
                <span class="log-time">2026-04-27 10:23:40</span>
                <span class="log-level">INFO</span>
                <span class="log-message">[RuleEngine] 规则 rule-001 执行成功</span>
              </div>
              <div class="log-line warning">
                <span class="log-time">2026-04-27 10:23:35</span>
                <span class="log-level">WARNING</span>
                <span class="log-message">[BACNET-01] 连接超时，正在重试...</span>
              </div>
              <div class="log-line error">
                <span class="log-time">2026-04-27 10:23:30</span>
                <span class="log-level">ERROR</span>
                <span class="log-message">[BACNET-01] 连接失败: Connection refused</span>
              </div>
              <div class="log-line debug">
                <span class="log-time">2026-04-27 10:23:25</span>
                <span class="log-level">DEBUG</span>
                <span class="log-message">[MQTT] 发布消息到 topic: xagent/data</span>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="activeMenu === 'backup'" class="settings-section">
          <h3>备份恢复</h3>
          <div class="backup-section">
            <el-card shadow="hover">
              <template #header>
                <span>配置备份</span>
              </template>
              <div class="backup-actions">
                <el-button type="primary">创建备份</el-button>
                <el-button>下载配置</el-button>
              </div>
              <div class="backup-list">
                <div class="backup-item">
                  <span class="backup-name">backup-2026-04-27.zip</span>
                  <span class="backup-time">2026-04-27 10:00:00</span>
                  <el-button type="primary" link size="small">恢复</el-button>
                  <el-button type="danger" link size="small">删除</el-button>
                </div>
                <div class="backup-item">
                  <span class="backup-name">backup-2026-04-26.zip</span>
                  <span class="backup-time">2026-04-26 10:00:00</span>
                  <el-button type="primary" link size="small">恢复</el-button>
                  <el-button type="danger" link size="small">删除</el-button>
                </div>
              </div>
            </el-card>
          </div>
        </div>
        
        <div v-if="activeMenu === 'users'" class="settings-section">
          <h3>用户管理</h3>
          <div class="user-section">
            <div class="section-header">
              <el-button type="primary">添加用户</el-button>
            </div>
            <el-table :data="[
              { username: 'admin', role: '管理员', status: 'active', lastLogin: '2026-04-27 09:00:00' },
              { username: 'operator', role: '操作员', status: 'active', lastLogin: '2026-04-26 14:30:00' }
            ]" stripe>
              <el-table-column prop="username" label="用户名" />
              <el-table-column prop="role" label="角色" />
              <el-table-column label="状态">
                <template #default>
                  <el-tag type="success" size="small">活跃</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="lastLogin" label="最后登录" />
              <el-table-column label="操作" width="150">
                <template #default>
                  <el-button type="primary" link size="small">编辑</el-button>
                  <el-button type="danger" link size="small">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
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

.settings-container {
  display: flex;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  min-height: calc(100vh - 200px);
}

.settings-sidebar {
  width: 200px;
  border-right: 1px solid #e0e0e0;
}

.settings-sidebar .el-menu {
  border-right: none;
}

.settings-content {
  flex: 1;
  padding: 24px;
}

.settings-section h3 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #2c3e50;
}

.settings-form {
  max-width: 600px;
}

.log-viewer {
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
}

.log-toolbar {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #2d2d2d;
}

.log-content {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 4px 0;
}

.log-time {
  color: #6a9955;
}

.log-level {
  width: 60px;
  font-weight: bold;
}

.log-line.info .log-level {
  color: #4ec9b0;
}

.log-line.warning .log-level {
  color: #dcdcaa;
}

.log-line.error .log-level {
  color: #f14c4c;
}

.log-line.debug .log-level {
  color: #608b4e;
}

.log-message {
  color: #d4d4d4;
}

.backup-section {
  max-width: 600px;
}

.backup-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.backup-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.backup-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.backup-name {
  flex: 1;
  font-weight: 500;
  color: #2c3e50;
}

.backup-time {
  color: #7f8c8d;
  font-size: 13px;
}

.user-section .section-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
</style>
