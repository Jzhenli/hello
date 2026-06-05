<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import {
  Setting,
  Document,
  Refresh,
  User,
  Lock,
  Plus,
  Edit,
  Check,
  Close,
  Download,
  Upload
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useUserStore } from '@/stores/users'
import { useResponsive } from '@/utils/useResponsive'
import type { UserInfo, RoleInfo } from '@/api/users'
import { configApi, type ConfigBackup } from '@/api/config'

const { isTablet, isMobile, isMediumTablet, width } = useResponsive()

// 优化布局判断：1280×800平板使用紧凑布局
const useCompactLayout = computed(() => {
  if (isMobile.value) return true
  if (isTablet.value) return true
  // 1280×800平板使用紧凑布局
  if (isMediumTablet.value) return true
  // 宽度小于1366的设备使用紧凑布局
  if (width.value <= 1366) return true
  return false
})

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

const userStore = useUserStore()

const RESOURCE_LABELS: Record<string, string> = {
  dashboard: '监控面板',
  devices: '设备管理',
  rules: '规则引擎',
  alerts: '告警配置',
  scada: '组态面板',
  settings: '系统设置',
  users: '用户管理',
  logs: '日志查看',
  backup: '配置管理',
  control: '控制命令',
}

const ACTION_LABELS: Record<string, string> = {
  view: '查看',
  create: '创建',
  update: '编辑',
  delete: '删除',
}

const userDialogVisible = ref(false)
const userDialogTitle = ref('添加用户')
const editingUserId = ref<number | null>(null)
const userForm = ref({
  username: '',
  password: '',
  display_name: '',
  email: '',
  role_name: '',
  status: 'active',
})

const roleDialogVisible = ref(false)
const roleDialogTitle = ref('添加角色')
const editingRoleName = ref<string | null>(null)
const roleForm = ref({
  name: '',
  display_name: '',
  description: '',
})

const passwordDialogVisible = ref(false)
const passwordUserId = ref<number | null>(null)
const passwordForm = ref({ new_password: '' })

const activePermissionRole = ref('')

const permissionEditData = ref<Record<string, Record<string, boolean>>>({})

const isEditingPermissions = ref(false)

const roleOptions = computed(() =>
  userStore.roles.map(r => ({ label: r.display_name, value: r.name }))
)

const currentRolePermissions = computed(() => {
  if (!activePermissionRole.value || !userStore.permissionMatrix) return null
  return userStore.permissionMatrix.roles.find(r => r.name === activePermissionRole.value)
})

function formatTime(timestamp: number | null): string {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

function getStatusType(status: string) {
  return status === 'active' ? 'success' : status === 'inactive' ? 'info' : 'danger'
}

function getStatusLabel(status: string) {
  return status === 'active' ? '活跃' : status === 'inactive' ? '禁用' : '锁定'
}

function openCreateUserDialog() {
  userDialogTitle.value = '添加用户'
  editingUserId.value = null
  userForm.value = { username: '', password: '', display_name: '', email: '', role_name: 'viewer', status: 'active' }
  userDialogVisible.value = true
}

function openEditUserDialog(user: UserInfo) {
  userDialogTitle.value = '编辑用户'
  editingUserId.value = user.id
  userForm.value = {
    username: user.username,
    password: '',
    display_name: user.display_name || '',
    email: user.email || '',
    role_name: user.role_name,
    status: user.status,
  }
  userDialogVisible.value = true
}

async function handleUserSubmit() {
  try {
    if (editingUserId.value) {
      const updateData: Record<string, string> = {}
      if (userForm.value.display_name) updateData.display_name = userForm.value.display_name
      if (userForm.value.email) updateData.email = userForm.value.email
      if (userForm.value.role_name) updateData.role_name = userForm.value.role_name
      if (userForm.value.status) updateData.status = userForm.value.status
      await userStore.updateUser(editingUserId.value, updateData)
      ElMessage.success('用户更新成功')
    } else {
      if (!userForm.value.username || !userForm.value.password) {
        ElMessage.warning('请填写用户名和密码')
        return
      }
      await userStore.createUser({
        username: userForm.value.username,
        password: userForm.value.password,
        role_name: userForm.value.role_name,
        display_name: userForm.value.display_name || undefined,
        email: userForm.value.email || undefined,
      })
      ElMessage.success('用户创建成功')
    }
    userDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDeleteUser(user: UserInfo) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${user.display_name || user.username}" 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await userStore.deleteUser(user.id)
    ElMessage.success('用户删除成功')
  } catch {
    // cancelled
  }
}

function openChangePasswordDialog(user: UserInfo) {
  passwordUserId.value = user.id
  passwordForm.value.new_password = ''
  passwordDialogVisible.value = true
}

async function handleChangePassword() {
  if (!passwordForm.value.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  try {
    const { userApi } = await import('@/api/users')
    await userApi.changePassword(passwordUserId.value!, passwordForm.value.new_password)
    ElMessage.success('密码修改成功')
    passwordDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '密码修改失败')
  }
}

function openCreateRoleDialog() {
  roleDialogTitle.value = '添加角色'
  editingRoleName.value = null
  roleForm.value = { name: '', display_name: '', description: '' }
  roleDialogVisible.value = true
}

function openEditRoleDialog(role: RoleInfo) {
  roleDialogTitle.value = '编辑角色'
  editingRoleName.value = role.name
  roleForm.value = {
    name: role.name,
    display_name: role.display_name,
    description: role.description || '',
  }
  roleDialogVisible.value = true
}

async function handleRoleSubmit() {
  try {
    if (editingRoleName.value) {
      await userStore.updateRole(editingRoleName.value, {
        display_name: roleForm.value.display_name,
        description: roleForm.value.description || undefined,
      })
      ElMessage.success('角色更新成功')
    } else {
      if (!roleForm.value.name || !roleForm.value.display_name) {
        ElMessage.warning('请填写角色标识和显示名称')
        return
      }
      await userStore.createRole({
        name: roleForm.value.name,
        display_name: roleForm.value.display_name,
        description: roleForm.value.description || undefined,
      })
      ElMessage.success('角色创建成功')
    }
    roleDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDeleteRole(role: RoleInfo) {
  if (role.is_system) {
    ElMessage.warning('系统内置角色不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除角色 "${role.display_name}" 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await userStore.deleteRole(role.name)
    ElMessage.success('角色删除成功')
  } catch {
    // cancelled
  }
}

function startEditPermissions() {
  if (!currentRolePermissions.value) return
  permissionEditData.value = JSON.parse(JSON.stringify(currentRolePermissions.value.permissions))
  isEditingPermissions.value = true
}

function cancelEditPermissions() {
  isEditingPermissions.value = false
  permissionEditData.value = {}
}

async function savePermissions() {
  try {
    await userStore.updatePermissionMatrix(activePermissionRole.value, permissionEditData.value)
    ElMessage.success('权限矩阵更新成功')
    isEditingPermissions.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '权限更新失败')
  }
}

function togglePermission(resource: string, action: string) {
  if (!permissionEditData.value[resource]) {
    permissionEditData.value[resource] = {}
  }
  permissionEditData.value[resource][action] = !permissionEditData.value[resource][action]
}

function selectAllForResource(resource: string) {
  if (!permissionEditData.value[resource]) {
    permissionEditData.value[resource] = {}
  }
  for (const action of (userStore.permissionMatrix?.actions || [])) {
    permissionEditData.value[resource][action] = true
  }
}

function clearAllForResource(resource: string) {
  if (!permissionEditData.value[resource]) {
    permissionEditData.value[resource] = {}
  }
  for (const action of (userStore.permissionMatrix?.actions || [])) {
    permissionEditData.value[resource][action] = false
  }
}

// ==================== 备份恢复相关 ====================
const backupList = ref<ConfigBackup[]>([])
const backupLoading = ref(false)
const exportLoading = ref(false)
const importLoading = ref(false)

// 加载备份列表
async function loadBackupList() {
  try {
    backupLoading.value = true
    const res = await configApi.listConfigs()
    backupList.value = res.configs
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载备份列表失败')
  } finally {
    backupLoading.value = false
  }
}

// 创建备份（导出配置）
async function handleCreateBackup() {
  try {
    exportLoading.value = true
    const res = await configApi.exportConfig()
    if (res.success) {
      ElMessage.success(`配置导出成功：${res.file} (${res.size_mb}MB)`)
      await loadBackupList()
    } else {
      ElMessage.error(res.error || '导出配置失败')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '导出配置失败')
  } finally {
    exportLoading.value = false
  }
}

// 下载配置文件（使用fetch + Blob URL，避免弹窗拦截）
async function handleDownloadConfig(backup?: ConfigBackup) {
  try {
    const filename = backup?.filename || (backupList.value.length > 0 ? backupList.value[0].filename : null)

    if (!filename) {
      ElMessage.warning('没有可下载的备份文件')
      return
    }

    const url = configApi.getDownloadUrl(filename)
    const token = configApi.getDownloadUrl(filename).split('token=')[1]

    // 使用fetch下载
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) {
      throw new Error(`下载失败: ${response.statusText}`)
    }

    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = filename
    a.click()
    URL.revokeObjectURL(downloadUrl)
  } catch (e: any) {
    ElMessage.error(e.message || '下载失败')
  }
}

// 导入配置
async function handleImportConfig(uploadFile: UploadFile) {
  const file = uploadFile.raw

  if (!file) return

  // 确认导入
  try {
    await ElMessageBox.confirm(
      '导入配置将覆盖当前配置，是否继续？',
      '确认导入',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      }
    )

    importLoading.value = true
    const res = await configApi.importConfig(file, true)

    if (res.success) {
      ElMessage.success(res.message)
      await loadBackupList()
    } else {
      ElMessage.error(res.error || '导入配置失败')
    }
  } catch {
    // 用户取消
  } finally {
    importLoading.value = false
  }
}

// 删除备份
async function handleDeleteBackup(backup: ConfigBackup) {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份文件 "${backup.filename}" 吗？`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      }
    )
    
    await configApi.deleteConfig(backup.filename)
    ElMessage.success('删除成功')
    await loadBackupList()
  } catch {
    // 用户取消
  }
}

// 恢复备份
async function handleRestoreBackup(backup: ConfigBackup) {
  try {
    await ElMessageBox.confirm(
      `恢复备份将覆盖当前配置，是否继续？`,
      '确认恢复',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      }
    )

    // 下载备份文件（添加超时控制）
    const url = configApi.getDownloadUrl(backup.filename)
    const token = url.split('token=')[1]

    // 使用AbortController实现超时控制
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000) // 30秒超时

    try {
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        },
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`下载失败: ${response.statusText}`)
      }

      const blob = await response.blob()
      const file = new File([blob], backup.filename, { type: 'application/zip' })

      importLoading.value = true
      const res = await configApi.importConfig(file, true)

      if (res.success) {
        ElMessage.success(res.message)
        await loadBackupList()
      } else {
        ElMessage.error(res.error || '恢复备份失败')
      }
    } catch (fetchError: any) {
      clearTimeout(timeoutId)
      if (fetchError.name === 'AbortError') {
        throw new Error('下载超时，请检查网络连接后重试')
      }
      throw fetchError
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || e.message || '恢复备份失败')
    }
  } finally {
    importLoading.value = false
  }
}

onMounted(async () => {
  userStore.restoreSession()
  await Promise.all([
    userStore.fetchUsers(),
    userStore.fetchRoles(),
    userStore.fetchPermissionMatrix(),
    loadBackupList(),
  ])
  if (userStore.permissionMatrix?.roles?.length) {
    activePermissionRole.value = userStore.permissionMatrix.roles[0].name
  }
})

watch(() => userStore.permissionMatrix, (matrix) => {
  if (matrix?.roles?.length && !activePermissionRole.value) {
    activePermissionRole.value = matrix.roles[0].name
  }
})
</script>

<template>
  <div class="settings-page">
    <div class="settings-container">
      <template v-if="!useCompactLayout">
        <div class="settings-sidebar">
          <el-menu :default-active="activeMenu" @select="(key: string) => activeMenu = key">
            <el-menu-item index="general">
              <el-icon><Setting /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('logs', 'view')" index="logs">
              <el-icon><Document /></el-icon>
              <span>日志查看</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('backup', 'view')" index="backup">
              <el-icon><Refresh /></el-icon>
              <span>配置管理</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('users', 'view')" index="users">
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('users', 'view')" index="permissions">
              <el-icon><Lock /></el-icon>
              <span>权限矩阵</span>
            </el-menu-item>
          </el-menu>
        </div>
      </template>

      <template v-else>
        <div class="settings-tabs">
          <div 
            class="settings-tab" 
            :class="{ active: activeMenu === 'general' }"
            @click="activeMenu = 'general'"
          >
            <el-icon><Setting /></el-icon>
            <span>系统配置</span>
          </div>
          <div 
            v-if="userStore.hasPermission('logs', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'logs' }"
            @click="activeMenu = 'logs'"
          >
            <el-icon><Document /></el-icon>
            <span>日志查看</span>
          </div>
          <div 
            v-if="userStore.hasPermission('backup', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'backup' }"
            @click="activeMenu = 'backup'"
          >
            <el-icon><Refresh /></el-icon>
            <span>配置管理</span>
          </div>
          <div 
            v-if="userStore.hasPermission('users', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'users' }"
            @click="activeMenu = 'users'"
          >
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </div>
          <div 
            v-if="userStore.hasPermission('users', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'permissions' }"
            @click="activeMenu = 'permissions'"
          >
            <el-icon><Lock /></el-icon>
            <span>权限矩阵</span>
          </div>
        </div>
      </template>

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
          <h3>配置管理</h3>
          <div class="backup-section">
            <!-- 操作按钮 -->
            <div class="backup-actions">
              <el-button 
                type="primary" 
                :icon="Refresh" 
                :loading="exportLoading"
                @click="handleCreateBackup"
              >
                导出配置
              </el-button>
              <el-upload
                :show-file-list="false"
                accept=".zip"
                :auto-upload="false"
                :disabled="importLoading"
                :on-change="handleImportConfig"
              >
                <el-button :icon="Upload" :loading="importLoading">导入配置</el-button>
              </el-upload>
              <el-button 
                :icon="Download" 
                :disabled="backupList.length === 0"
                @click="handleDownloadConfig()"
              >
                下载最新备份
              </el-button>
            </div>

            <!-- 备份列表 -->
            <el-table 
              :data="backupList" 
              v-loading="backupLoading"
              stripe
              style="width: 100%"
            >
              <el-table-column label="文件名" min-width="200">
                <template #default="{ row, $index }">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon style="color: #409eff;"><Document /></el-icon>
                    <span>{{ row.filename }}</span>
                    <el-tag v-if="$index === 0" type="success" size="small">最新</el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="100" align="center">
                <template #default="{ row }">
                  {{ row.size_mb }} MB
                </template>
              </el-table-column>
              <el-table-column label="创建时间" width="170" align="center">
                <template #default="{ row }">
                  {{ row.created_at.replace('T', ' ').substring(0, 19) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" align="center">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="handleRestoreBackup(row)">恢复</el-button>
                  <el-button type="default" link size="small" @click="handleDownloadConfig(row)">下载</el-button>
                  <el-button type="danger" link size="small" @click="handleDeleteBackup(row)">删除</el-button>
                </template>
              </el-table-column>
              
              <template #empty>
                <el-empty description="暂无备份文件">
                  <el-button type="primary" size="small" @click="handleCreateBackup">立即创建</el-button>
                </el-empty>
              </template>
            </el-table>
          </div>
        </div>

        <div v-if="activeMenu === 'users'" class="settings-section">
          <h3>用户管理</h3>
          <div class="user-section">
            <el-card shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span class="card-title">用户列表</span>
                  <el-button v-if="userStore.hasPermission('users', 'create')" type="primary" :icon="Plus" size="small" @click="openCreateUserDialog">添加用户</el-button>
                </div>
              </template>
              <el-table :data="userStore.users" stripe v-loading="userStore.loading">
                <el-table-column prop="username" label="用户名" min-width="90" />
                <el-table-column prop="display_name" label="显示名称" min-width="90" />
                <el-table-column label="角色" min-width="90">
                  <template #default="{ row }">
                    <el-tag size="small">{{ row.role_display_name || row.role_name }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="最后登录" min-width="140">
                  <template #default="{ row }">
                    {{ formatTime(row.last_login) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="180" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="primary" link size="small" @click="openEditUserDialog(row)">编辑</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="warning" link size="small" @click="openChangePasswordDialog(row)">改密</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'delete')" type="danger" link size="small" @click="handleDeleteUser(row)" :disabled="row.username === 'admin'">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-card shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span class="card-title">角色列表</span>
                  <el-button v-if="userStore.hasPermission('users', 'create')" type="primary" :icon="Plus" size="small" @click="openCreateRoleDialog">添加角色</el-button>
                </div>
              </template>
              <el-table :data="userStore.roles" stripe>
                <el-table-column prop="name" label="角色标识" min-width="90" />
                <el-table-column prop="display_name" label="显示名称" min-width="90" />
                <el-table-column prop="description" label="描述" min-width="140" />
                <el-table-column label="类型" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.is_system ? 'info' : 'success'" size="small">
                      {{ row.is_system ? '系统' : '自定义' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="primary" link size="small" @click="openEditRoleDialog(row)">编辑</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'delete')" type="danger" link size="small" @click="handleDeleteRole(row)" :disabled="row.is_system">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>
        </div>

        <div v-if="activeMenu === 'permissions'" class="settings-section">
          <h3>权限矩阵</h3>
          <div class="permission-section">
            <div class="permission-toolbar">
              <el-select v-model="activePermissionRole" placeholder="选择角色" style="width: 200px">
                <el-option
                  v-for="role in userStore.permissionMatrix?.roles || []"
                  :key="role.name"
                  :label="role.display_name"
                  :value="role.name"
                />
              </el-select>
              <div v-if="!isEditingPermissions && userStore.hasPermission('users', 'update')" class="permission-actions">
                <el-button type="primary" :icon="Edit" @click="startEditPermissions">编辑权限</el-button>
              </div>
              <div v-else class="permission-actions">
                <el-button type="success" :icon="Check" @click="savePermissions">保存</el-button>
                <el-button :icon="Close" @click="cancelEditPermissions">取消</el-button>
              </div>
            </div>

            <div v-if="userStore.permissionMatrix && activePermissionRole" class="permission-matrix">
              <table class="matrix-table">
                <thead>
                  <tr>
                    <th class="resource-header">资源 / 操作</th>
                    <th v-for="action in userStore.permissionMatrix.actions" :key="action" class="action-header">
                      {{ ACTION_LABELS[action] || action }}
                    </th>
                    <th v-if="isEditingPermissions" class="action-header">快捷操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="resource in userStore.permissionMatrix.resources" :key="resource">
                    <td class="resource-cell">{{ RESOURCE_LABELS[resource] || resource }}</td>
                    <td v-for="action in userStore.permissionMatrix.actions" :key="`${resource}-${action}`" class="permission-cell">
                      <template v-if="isEditingPermissions">
                        <el-checkbox
                          :model-value="permissionEditData[resource]?.[action] ?? false"
                          @change="togglePermission(resource, action)"
                        />
                      </template>
                      <template v-else>
                        <el-icon v-if="currentRolePermissions?.permissions?.[resource]?.[action]" class="perm-allowed"><Check /></el-icon>
                        <el-icon v-else class="perm-denied"><Close /></el-icon>
                      </template>
                    </td>
                    <td v-if="isEditingPermissions" class="shortcut-cell">
                      <el-button link type="primary" size="small" @click="selectAllForResource(resource)">全选</el-button>
                      <el-button link type="danger" size="small" @click="clearAllForResource(resource)">清空</el-button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="!activePermissionRole && userStore.permissionMatrix" class="empty-hint">
              请从上方下拉框选择一个角色查看权限配置
            </div>

            <div class="permission-legend">
              <span class="legend-item"><el-icon class="perm-allowed"><Check /></el-icon> 允许</span>
              <span class="legend-item"><el-icon class="perm-denied"><Close /></el-icon> 拒绝</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="userDialogVisible" :title="userDialogTitle" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="用户名" v-if="!editingUserId">
          <el-input v-model="userForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="用户名" v-else>
          <el-input :model-value="userForm.username" disabled />
        </el-form-item>
        <el-form-item label="密码" v-if="!editingUserId">
          <el-input v-model="userForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="userForm.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_name" style="width: 100%">
            <el-option v-for="opt in roleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" v-if="editingUserId">
          <el-select v-model="userForm.status" style="width: 100%">
            <el-option label="活跃" value="active" />
            <el-option label="禁用" value="inactive" />
            <el-option label="锁定" value="locked" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUserSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" :title="roleDialogTitle" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="角色标识" v-if="!editingRoleName">
          <el-input v-model="roleForm.name" placeholder="请输入角色标识（英文）" />
        </el-form-item>
        <el-form-item label="角色标识" v-else>
          <el-input :model-value="roleForm.name" disabled />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="roleForm.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" placeholder="请输入角色描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRoleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="min(400px, 90vw)" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 0;
}

.settings-container {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  min-height: calc(100vh - 160px);
}

@media (min-width: 1025px) {
  .settings-container {
    flex-direction: row;
    min-height: calc(100vh - 200px);
  }
}

.settings-sidebar {
  width: 200px;
  border-right: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.settings-mobile-nav {
  display: none;
}

.mobile-nav-title {
  display: none;
}

.settings-mobile-menu {
  display: none;
}

.settings-tabs {
  display: flex;
  background: #fff;
  border-radius: 8px 8px 0 0;
  padding: 4px;
  gap: 4px;
  flex-shrink: 0;
  border-bottom: 1px solid #e0e0e0;
  overflow-x: auto;
}

.settings-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  background: transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.settings-tab:hover {
  background: #f5f7fa;
}

.settings-tab.active {
  background: #409eff;
  color: #fff;
}

.settings-tab .el-icon {
  font-size: 16px;
}

.settings-sidebar .el-menu {
  border-right: none;
}

.settings-content {
  flex: 1;
  padding: 24px;
  overflow-x: auto;
  min-width: 0;
}

@media (max-width: 1024px) {
  .settings-content {
    padding: 16px;
  }
}

@media (max-width: 768px) {
  .settings-content {
    padding: 12px;
  }
}

@media (max-height: 700px) {
  .settings-section h3 {
    margin: 0 0 12px 0;
    font-size: 16px;
  }

  .settings-content {
    padding: 12px;
  }

  .settings-tabs {
    padding: 2px;
    gap: 2px;
  }

  .settings-tab {
    padding: 6px 10px;
    font-size: 13px;
  }
}

/* 中平板优化 (1280×800) */
@media (min-width: 1025px) and (max-width: 1366px) {
  .settings-container {
    flex-direction: column;
    min-height: calc(100vh - 180px);
  }

  .settings-tabs {
    padding: 6px;
    gap: 6px;
  }

  .settings-tab {
    padding: 10px 14px;
    font-size: 14px;
  }

  .settings-content {
    padding: 16px;
    overflow-x: auto;
  }

  .settings-section h3 {
    font-size: 16px;
    margin-bottom: 16px;
  }

  .section-card {
    margin-bottom: 16px;
  }

  .section-card :deep(.el-card__header) {
    padding: 10px 16px;
  }

  .card-title {
    font-size: 13px;
  }

  /* 表格优化 */
  .el-table {
    font-size: 13px;
  }

  .el-table th {
    padding: 8px 0;
  }

  .el-table td {
    padding: 8px 0;
  }

  /* 表格横向滚动 */
  .section-card :deep(.el-table__body-wrapper) {
    overflow-x: auto;
    position: relative;
  }

  /* 表格横向滚动提示 - 右侧渐变阴影 */
  .section-card :deep(.el-table__body-wrapper)::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 30px;
    background: linear-gradient(to left, rgba(255, 255, 255, 0.9), transparent);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.3s;
  }

  /* 当表格内容超出时显示滚动提示 */
  .section-card :deep(.el-table__body-wrapper:hover)::after {
    opacity: 1;
  }

  /* 表格内容不换行 */
  .el-table .cell {
    white-space: nowrap;
  }

  /* 权限矩阵优化 */
  .matrix-table {
    font-size: 13px;
  }

  .matrix-table th,
  .matrix-table td {
    padding: 8px 12px;
  }

  .resource-header,
  .action-header {
    min-width: 80px;
  }

  .resource-header {
    min-width: 100px;
  }

  /* 表单优化 */
  .settings-form {
    max-width: 100%;
  }

  .el-form-item {
    margin-bottom: 16px;
  }

  .el-form-item__label {
    font-size: 13px;
  }

  /* 日志查看优化 */
  .log-content {
    font-size: 12px;
    max-height: 300px;
  }

  .log-line {
    gap: 8px;
  }

  .log-time {
    font-size: 11px;
  }

  .log-level {
    width: 50px;
    font-size: 11px;
  }

  /* 备份列表优化 */
  .backup-item {
    padding: 10px;
    font-size: 13px;
  }

  .backup-name {
    font-size: 13px;
  }

  .backup-time {
    font-size: 12px;
  }

  /* 用户管理卡片优化 */
  .user-section {
    gap: 12px;
  }

  /* 操作按钮优化 */
  .el-table .el-button + .el-button {
    margin-left: 4px;
  }

  /* 权限矩阵容器优化 */
  .permission-matrix {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
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
  max-width: 1000px;
}

.backup-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.user-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  border: 1px solid #ebeef5;
}

.section-card :deep(.el-card__header) {
  padding: 12px 20px;
  background: #fafafa;
  border-bottom: 1px solid #ebeef5;
}

.section-card :deep(.el-card__body) {
  padding: 0;
}

.section-card :deep(.el-table) {
  border-radius: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.permission-section {
  max-width: 100%;
}

.permission-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.permission-actions {
  display: flex;
  gap: 8px;
}

.permission-matrix {
  overflow-x: auto;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.matrix-table th,
.matrix-table td {
  border: 1px solid #e0e0e0;
  padding: 10px 16px;
  text-align: center;
}

.resource-header {
  background: #f5f7fa;
  font-weight: 600;
  color: #2c3e50;
  text-align: left;
  min-width: 120px;
}

.action-header {
  background: #f5f7fa;
  font-weight: 600;
  color: #2c3e50;
  min-width: 80px;
}

.resource-cell {
  text-align: left;
  font-weight: 500;
  color: #2c3e50;
  background: #fafafa;
}

.permission-cell {
  vertical-align: middle;
}

.shortcut-cell {
  vertical-align: middle;
  white-space: nowrap;
}

.perm-allowed {
  color: #27ae60;
  font-size: 18px;
}

.perm-denied {
  color: #e74c3c;
  font-size: 18px;
}

.permission-legend {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 13px;
  color: #7f8c8d;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.empty-hint {
  text-align: center;
  padding: 40px;
  color: #909399;
  font-size: 14px;
}
</style>
