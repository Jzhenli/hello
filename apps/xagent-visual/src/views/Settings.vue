<template>
  <div class="settings-page">
    <div class="settings-container">
      <template v-if="!useCompactLayout">
        <div class="settings-sidebar">
          <el-menu :default-active="activeMenu" @select="(key: string) => activeMenu = key">
            <el-menu-item index="general">
              <el-icon><Setting /></el-icon>
              <span>{{ $t('settings.menu.general') }}</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('logs', 'view')" index="logs">
              <el-icon><Document /></el-icon>
              <span>{{ $t('settings.menu.logs') }}</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('backup', 'view')" index="backup">
              <el-icon><Refresh /></el-icon>
              <span>{{ $t('settings.menu.backup') }}</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('users', 'view')" index="users">
              <el-icon><User /></el-icon>
              <span>{{ $t('settings.menu.users') }}</span>
            </el-menu-item>
            <el-menu-item v-if="userStore.hasPermission('users', 'view')" index="permissions">
              <el-icon><Lock /></el-icon>
              <span>{{ $t('settings.menu.permissions') }}</span>
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
            <span>{{ $t('settings.menu.general') }}</span>
          </div>
          <div 
            v-if="userStore.hasPermission('logs', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'logs' }"
            @click="activeMenu = 'logs'"
          >
            <el-icon><Document /></el-icon>
            <span>{{ $t('settings.menu.logs') }}</span>
          </div>
          <div 
            v-if="userStore.hasPermission('backup', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'backup' }"
            @click="activeMenu = 'backup'"
          >
            <el-icon><Refresh /></el-icon>
            <span>{{ $t('settings.menu.backup') }}</span>
          </div>
          <div 
            v-if="userStore.hasPermission('users', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'users' }"
            @click="activeMenu = 'users'"
          >
            <el-icon><User /></el-icon>
            <span>{{ $t('settings.menu.users') }}</span>
          </div>
          <div 
            v-if="userStore.hasPermission('users', 'view')"
            class="settings-tab" 
            :class="{ active: activeMenu === 'permissions' }"
            @click="activeMenu = 'permissions'"
          >
            <el-icon><Lock /></el-icon>
            <span>{{ $t('settings.menu.permissions') }}</span>
          </div>
        </div>
      </template>

      <div class="settings-content">
        <div v-if="activeMenu === 'general'" class="settings-section">
          <h3>{{ $t('settings.menu.general') }}</h3>
          <el-form label-width="120px" class="settings-form">
            <el-form-item :label="$t('settings.general.log_level')">
              <el-select v-model="systemConfig.logLevel" style="width: 200px">
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('settings.general.data_retention')">
              <el-input-number v-model="systemConfig.dataRetention" :min="1" :max="365" />
            </el-form-item>
            <el-form-item :label="$t('settings.general.max_connections')">
              <el-input-number v-model="systemConfig.maxConnections" :min="1" :max="1000" />
            </el-form-item>
            <el-form-item :label="$t('settings.general.timeout')">
              <el-input-number v-model="systemConfig.timeout" :min="1" :max="300" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSave">{{ $t('settings.general.save_config') }}</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div v-if="activeMenu === 'logs'" class="settings-section">
          <h3>{{ $t('settings.menu.logs') }}</h3>
          <div class="log-viewer">
            <div class="log-toolbar">
              <el-select :placeholder="$t('settings.log.level')" style="width: 120px">
                <el-option :label="$t('settings.log.all')" value="" />
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
              </el-select>
              <el-button type="primary">{{ $t('common.refresh') }}</el-button>
              <el-button>{{ $t('settings.log.download') }}</el-button>
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
          <h3>{{ $t('settings.menu.backup') }}</h3>
          <div class="backup-section">
            <!-- 操作按钮 -->
            <div class="backup-actions">
              <el-button 
                type="primary" 
                :icon="Refresh" 
                :loading="exportLoading"
                @click="handleCreateBackup"
              >
                {{ $t('settings.backup.export') }}
              </el-button>
              <el-upload
                :show-file-list="false"
                accept=".zip"
                :auto-upload="false"
                :disabled="importLoading"
                :on-change="handleImportConfig"
              >
                <el-button :icon="Upload" :loading="importLoading">{{ $t('settings.backup.import') }}</el-button>
              </el-upload>
              <el-button 
                :icon="Download" 
                :disabled="backupList.length === 0"
                @click="handleDownloadConfig()"
              >
                {{ $t('settings.backup.download_latest') }}
              </el-button>
            </div>

            <!-- 备份列表 -->
            <el-table 
              :data="backupList" 
              v-loading="backupLoading"
              stripe
              style="width: 100%"
            >
              <el-table-column :label="$t('settings.backup.filename')" min-width="200">
                <template #default="{ row, $index }">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-icon style="color: var(--color-primary);"><Document /></el-icon>
                    <span>{{ row.filename }}</span>
                    <el-tag v-if="$index === 0" type="success" size="small">{{ $t('settings.backup.latest') }}</el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column :label="$t('settings.backup.size')" width="100" align="center">
                <template #default="{ row }">
                  {{ row.size_mb }} MB
                </template>
              </el-table-column>
              <el-table-column :label="$t('settings.backup.created_at')" width="170" align="center">
                <template #default="{ row }">
                  {{ row.created_at.replace('T', ' ').substring(0, 19) }}
                </template>
              </el-table-column>
              <el-table-column :label="$t('settings.actions_label')" width="200" align="center">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="handleRestoreBackup(row)">{{ $t('settings.backup.restore') }}</el-button>
                  <el-button type="default" link size="small" @click="handleDownloadConfig(row)">{{ $t('settings.backup.download') }}</el-button>
                  <el-button type="danger" link size="small" @click="handleDeleteBackup(row)">{{ $t('common.delete') }}</el-button>
                </template>
              </el-table-column>
              
              <template #empty>
                <el-empty :description="$t('settings.backup.no_backup')">
                  <el-button type="primary" size="small" @click="handleCreateBackup">{{ $t('settings.backup.create_now') }}</el-button>
                </el-empty>
              </template>
            </el-table>
          </div>
        </div>

        <div v-if="activeMenu === 'users'" class="settings-section">
          <h3>{{ $t('settings.menu.users') }}</h3>
          <div class="user-section">
            <el-card shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span class="card-title">{{ $t('settings.user.list_title') }}</span>
                  <el-button v-if="userStore.hasPermission('users', 'create')" type="primary" :icon="Plus" size="small" @click="openCreateUserDialog">{{ $t('settings.user.add') }}</el-button>
                </div>
              </template>
              <el-table :data="userStore.users" stripe v-loading="userStore.loading">
                <el-table-column prop="username" :label="$t('settings.user.username')" min-width="90" />
                <el-table-column prop="display_name" :label="$t('settings.user.display_name')" min-width="90" />
                <el-table-column :label="$t('settings.user.role')" min-width="90">
                  <template #default="{ row }">
                    <el-tag size="small">{{ row.role_display_name || row.role_name }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('settings.user.status')" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('settings.user.last_login')" min-width="140">
                  <template #default="{ row }">
                    {{ formatTime(row.last_login) }}
                  </template>
                </el-table-column>
                <el-table-column :label="$t('settings.actions_label')" width="180" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="primary" link size="small" @click="openEditUserDialog(row)">{{ $t('common.edit') }}</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="warning" link size="small" @click="openChangePasswordDialog(row)">{{ $t('settings.user.change_password') }}</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'delete')" type="danger" link size="small" @click="handleDeleteUser(row)" :disabled="row.username === 'admin'">{{ $t('common.delete') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-card shadow="never" class="section-card">
              <template #header>
                <div class="card-header">
                  <span class="card-title">{{ $t('settings.role.list_title') }}</span>
                  <el-button v-if="userStore.hasPermission('users', 'create')" type="primary" :icon="Plus" size="small" @click="openCreateRoleDialog">{{ $t('settings.role.add') }}</el-button>
                </div>
              </template>
              <el-table :data="userStore.roles" stripe>
                <el-table-column prop="name" :label="$t('settings.role.name')" min-width="90" />
                <el-table-column prop="display_name" :label="$t('settings.user.display_name')" min-width="90" />
                <el-table-column prop="description" :label="$t('settings.role.description')" min-width="140" />
                <el-table-column :label="$t('settings.role.type')" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.is_system ? 'info' : 'success'" size="small">
                      {{ row.is_system ? $t('settings.role.system') : $t('settings.role.custom') }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('settings.actions_label')" width="120" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button v-if="userStore.hasPermission('users', 'update')" type="primary" link size="small" @click="openEditRoleDialog(row)">{{ $t('common.edit') }}</el-button>
                    <el-button v-if="userStore.hasPermission('users', 'delete')" type="danger" link size="small" @click="handleDeleteRole(row)" :disabled="row.is_system">{{ $t('common.delete') }}</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>
        </div>

        <div v-if="activeMenu === 'permissions'" class="settings-section">
          <h3>{{ $t('settings.menu.permissions') }}</h3>
          <div class="permission-section">
            <div class="permission-toolbar">
              <el-select v-model="activePermissionRole" :placeholder="$t('settings.permission.select_role')" style="width: 200px">
                <el-option
                  v-for="role in userStore.permissionMatrix?.roles || []"
                  :key="role.name"
                  :label="role.display_name"
                  :value="role.name"
                />
              </el-select>
              <div v-if="!isEditingPermissions && userStore.hasPermission('users', 'update')" class="permission-actions">
                <el-button type="primary" :icon="Edit" @click="startEditPermissions">{{ $t('settings.permission.edit') }}</el-button>
              </div>
              <div v-else class="permission-actions">
                <el-button type="success" :icon="Check" @click="savePermissions">{{ $t('common.save') }}</el-button>
                <el-button :icon="Close" @click="cancelEditPermissions">{{ $t('common.cancel') }}</el-button>
              </div>
            </div>

            <div v-if="userStore.permissionMatrix && activePermissionRole" class="permission-matrix">
              <table class="matrix-table">
                <thead>
                  <tr>
                    <th class="resource-header">{{ $t('settings.permission.resource_action') }}</th>
                    <th v-for="action in userStore.permissionMatrix.actions" :key="action" class="action-header">
                      {{ ACTION_LABELS[action] || action }}
                    </th>
                    <th v-if="isEditingPermissions" class="action-header">{{ $t('settings.permission.quick_action') }}</th>
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
                      <el-button link type="primary" size="small" @click="selectAllForResource(resource)">{{ $t('settings.permission.select_all') }}</el-button>
                      <el-button link type="danger" size="small" @click="clearAllForResource(resource)">{{ $t('settings.permission.clear_all') }}</el-button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="!activePermissionRole && userStore.permissionMatrix" class="empty-hint">
              {{ $t('settings.permission.select_role_hint') }}
            </div>

            <div class="permission-legend">
              <span class="legend-item"><el-icon class="perm-allowed"><Check /></el-icon> {{ $t('settings.permission.allowed') }}</span>
              <span class="legend-item"><el-icon class="perm-denied"><Close /></el-icon> {{ $t('settings.permission.denied') }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="userDialogVisible" :title="userDialogTitle" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item :label="$t('settings.user.username')" v-if="!editingUserId">
          <el-input v-model="userForm.username" :placeholder="$t('settings.user.username_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.user.username')" v-else>
          <el-input :model-value="userForm.username" disabled />
        </el-form-item>
        <el-form-item :label="$t('settings.user.password')" v-if="!editingUserId">
          <el-input v-model="userForm.password" type="password" show-password :placeholder="$t('settings.user.password_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.user.display_name')">
          <el-input v-model="userForm.display_name" :placeholder="$t('settings.user.display_name_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.user.email')">
          <el-input v-model="userForm.email" :placeholder="$t('settings.user.email_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.user.role')">
          <el-select v-model="userForm.role_name" style="width: 100%">
            <el-option v-for="opt in roleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.user.status')" v-if="editingUserId">
          <el-select v-model="userForm.status" style="width: 100%">
            <el-option :label="$t('settings.status.active')" value="active" />
            <el-option :label="$t('settings.status.inactive')" value="inactive" />
            <el-option :label="$t('settings.status.locked')" value="locked" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleUserSubmit">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" :title="roleDialogTitle" width="min(480px, 92vw)" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item :label="$t('settings.role.name')" v-if="!editingRoleName">
          <el-input v-model="roleForm.name" :placeholder="$t('settings.role.name_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.role.name')" v-else>
          <el-input :model-value="roleForm.name" disabled />
        </el-form-item>
        <el-form-item :label="$t('settings.user.display_name')">
          <el-input v-model="roleForm.display_name" :placeholder="$t('settings.user.display_name_placeholder')" />
        </el-form-item>
        <el-form-item :label="$t('settings.role.description')">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" :placeholder="$t('settings.role.description_placeholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleRoleSubmit">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" :title="$t('settings.password.title')" width="min(400px, 90vw)" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item :label="$t('settings.password.new_password')">
          <el-input v-model="passwordForm.new_password" type="password" show-password :placeholder="$t('settings.password.new_password_placeholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleChangePassword">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()

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
  ElMessage.success(t('settings.config_saved'))
}

const userStore = useUserStore()

const RESOURCE_LABELS: Record<string, string> = {
  dashboard: t('settings.resources.dashboard'),
  devices: t('settings.resources.devices'),
  rules: t('settings.resources.rules'),
  alerts: t('settings.resources.alerts'),
  scada: t('settings.resources.scada'),
  settings: t('settings.resources.settings'),
  users: t('settings.resources.users'),
  logs: t('settings.resources.logs'),
  backup: t('settings.resources.backup'),
  control: t('settings.resources.control'),
}

const ACTION_LABELS: Record<string, string> = {
  view: t('settings.actions.view'),
  create: t('settings.actions.create'),
  update: t('settings.actions.update'),
  delete: t('settings.actions.delete'),
}

const userDialogVisible = ref(false)
const userDialogTitle = ref(t('settings.user.add_title'))
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
const roleDialogTitle = ref(t('settings.role.add_title'))
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
  return status === 'active' ? t('settings.status.active') : status === 'inactive' ? t('settings.status.inactive') : t('settings.status.locked')
}

function openCreateUserDialog() {
  userDialogTitle.value = t('settings.user.add_title')
  editingUserId.value = null
  userForm.value = { username: '', password: '', display_name: '', email: '', role_name: 'viewer', status: 'active' }
  userDialogVisible.value = true
}

function openEditUserDialog(user: UserInfo) {
  userDialogTitle.value = t('settings.user.edit_title')
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
      ElMessage.success(t('settings.user.update_success'))
    } else {
      if (!userForm.value.username || !userForm.value.password) {
        ElMessage.warning(t('settings.user.fill_username_password'))
        return
      }
      await userStore.createUser({
        username: userForm.value.username,
        password: userForm.value.password,
        role_name: userForm.value.role_name,
        display_name: userForm.value.display_name || undefined,
        email: userForm.value.email || undefined,
      })
      ElMessage.success(t('settings.user.create_success'))
    }
    userDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('settings.operation_failed'))
  }
}

async function handleDeleteUser(user: UserInfo) {
  try {
    await ElMessageBox.confirm(t('settings.user.delete_confirm_msg', { name: user.display_name || user.username }), t('settings.delete_confirm'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    await userStore.deleteUser(user.id)
    ElMessage.success(t('settings.user.delete_success'))
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
    ElMessage.warning(t('settings.password.enter_new'))
    return
  }
  try {
    const { userApi } = await import('@/api/users')
    await userApi.changePassword(passwordUserId.value!, passwordForm.value.new_password)
    ElMessage.success(t('settings.password.change_success'))
    passwordDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('settings.password.change_failed'))
  }
}

function openCreateRoleDialog() {
  roleDialogTitle.value = t('settings.role.add_title')
  editingRoleName.value = null
  roleForm.value = { name: '', display_name: '', description: '' }
  roleDialogVisible.value = true
}

function openEditRoleDialog(role: RoleInfo) {
  roleDialogTitle.value = t('settings.role.edit_title')
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
      ElMessage.success(t('settings.role.update_success'))
    } else {
      if (!roleForm.value.name || !roleForm.value.display_name) {
        ElMessage.warning(t('settings.role.fill_name_display'))
        return
      }
      await userStore.createRole({
        name: roleForm.value.name,
        display_name: roleForm.value.display_name,
        description: roleForm.value.description || undefined,
      })
      ElMessage.success(t('settings.role.create_success'))
    }
    roleDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('settings.operation_failed'))
  }
}

async function handleDeleteRole(role: RoleInfo) {
  if (role.is_system) {
    ElMessage.warning(t('settings.role.system_cannot_delete'))
    return
  }
  try {
    await ElMessageBox.confirm(t('settings.role.delete_confirm_msg', { name: role.display_name }), t('settings.delete_confirm'), {
      type: 'warning',
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    await userStore.deleteRole(role.name)
    ElMessage.success(t('settings.role.delete_success'))
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
    ElMessage.success(t('settings.permission.update_success'))
    isEditingPermissions.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('settings.permission.update_failed'))
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
    ElMessage.error(e.response?.data?.detail || t('settings.backup.load_failed'))
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
      ElMessage.success(t('settings.backup.export_success', { file: res.file, size: res.size_mb }))
      await loadBackupList()
    } else {
      ElMessage.error(res.error || t('settings.backup.export_failed'))
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || t('settings.backup.export_failed'))
  } finally {
    exportLoading.value = false
  }
}

// 下载配置文件（使用fetch + Blob URL，避免弹窗拦截）
async function handleDownloadConfig(backup?: ConfigBackup) {
  try {
    const filename = backup?.filename || (backupList.value.length > 0 ? backupList.value[0].filename : null)

    if (!filename) {
      ElMessage.warning(t('settings.backup.no_downloadable'))
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
      throw new Error(`${t('settings.backup.download_failed')}: ${response.statusText}`)
    }

    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = filename
    a.click()
    URL.revokeObjectURL(downloadUrl)
  } catch (e: any) {
    ElMessage.error(e.message || t('settings.backup.download_failed'))
  }
}

// 导入配置
async function handleImportConfig(uploadFile: UploadFile) {
  const file = uploadFile.raw

  if (!file) return

  // 确认导入
  try {
    await ElMessageBox.confirm(
      t('settings.backup.import_confirm'),
      t('settings.backup.import_confirm_title'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      }
    )

    importLoading.value = true
    const res = await configApi.importConfig(file, true)

    if (res.success) {
      ElMessage.success(res.message)
      await loadBackupList()
    } else {
      ElMessage.error(res.error || t('settings.backup.import_failed'))
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
      t('settings.backup.delete_confirm_msg', { filename: backup.filename }),
      t('settings.delete_confirm'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      }
    )
    
    await configApi.deleteConfig(backup.filename)
    ElMessage.success(t('settings.backup.delete_success'))
    await loadBackupList()
  } catch {
    // 用户取消
  }
}

// 恢复备份
async function handleRestoreBackup(backup: ConfigBackup) {
  try {
    await ElMessageBox.confirm(
      t('settings.backup.restore_confirm'),
      t('settings.backup.restore_confirm_title'),
      {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
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
        throw new Error(`${t('settings.backup.download_failed')}: ${response.statusText}`)
      }

      const blob = await response.blob()
      const file = new File([blob], backup.filename, { type: 'application/zip' })

      importLoading.value = true
      const res = await configApi.importConfig(file, true)

      if (res.success) {
        ElMessage.success(res.message)
        await loadBackupList()
      } else {
        ElMessage.error(res.error || t('settings.backup.restore_failed'))
      }
    } catch (fetchError: any) {
      clearTimeout(timeoutId)
      if (fetchError.name === 'AbortError') {
        throw new Error(t('settings.backup.download_timeout'))
      }
      throw fetchError
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || e.message || t('settings.backup.restore_failed'))
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

<style scoped>
.settings-page {
  padding: 0;
}

.settings-container {
  display: flex;
  flex-direction: column;
  background: var(--bg-container);
  border-radius: 8px;
  box-shadow: var(--shadow-light);
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
  border-right: 1px solid var(--border-base);
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
  background: var(--bg-container);
  border-radius: 8px 8px 0 0;
  padding: 4px;
  gap: 4px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-base);
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
  color: var(--text-secondary);
  background: transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.settings-tab:hover {
  background: var(--bg-hover);
}

.settings-tab.active {
  background: var(--color-primary);
  color: var(--text-white);
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
  color: var(--text-primary);
}

.settings-form {
  max-width: 600px;
}

.log-viewer {
  background: var(--code-bg, #1e1e1e);
  border-radius: 8px;
  overflow: hidden;
}

.log-toolbar {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--code-toolbar-bg, #2d2d2d);
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
  color: var(--code-comment, #6a9955);
}

.log-level {
  width: 60px;
  font-weight: bold;
}

.log-line.info .log-level {
  color: var(--code-function, #4ec9b0);
}

.log-line.warning .log-level {
  color: var(--code-variable, #dcdcaa);
}

.log-line.error .log-level {
  color: var(--code-string, #f14c4c);
}

.log-line.debug .log-level {
  color: var(--code-keyword, #608b4e);
}

.log-message {
  color: var(--code-text, #d4d4d4);
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
  border: 1px solid var(--border-light);
}

.section-card :deep(.el-card__header) {
  padding: 12px 20px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border-light);
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
  color: var(--text-primary);
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
  border: 1px solid var(--border-base);
  padding: 10px 16px;
  text-align: center;
}

.resource-header {
  background: var(--bg-hover);
  font-weight: 600;
  color: var(--text-primary);
  text-align: left;
  min-width: 120px;
}

.action-header {
  background: var(--bg-hover);
  font-weight: 600;
  color: var(--text-primary);
  min-width: 80px;
}

.resource-cell {
  text-align: left;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-hover);
}

.permission-cell {
  vertical-align: middle;
}

.shortcut-cell {
  vertical-align: middle;
  white-space: nowrap;
}

.perm-allowed {
  color: var(--color-success);
  font-size: 18px;
}

.perm-denied {
  color: var(--color-danger);
  font-size: 18px;
}

.permission-legend {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  padding: 12px;
  background: var(--bg-hover);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.empty-hint {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
