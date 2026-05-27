import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { userApi, type UserInfo, type RoleInfo, type PermissionMatrix } from '@/api/users'

export const useUserStore = defineStore('user', () => {
  const currentUser = ref<UserInfo | null>(null)
  const users = ref<UserInfo[]>([])
  const roles = ref<RoleInfo[]>([])
  const permissionMatrix = ref<PermissionMatrix | null>(null)
  const _loadingCount = ref(0)
  const isAuthenticated = ref(false)

  const loading = computed(() => _loadingCount.value > 0)

  const isLoggedIn = computed(() => isAuthenticated.value && currentUser.value !== null)

  const currentUserPermissions = computed(() => {
    if (!currentUser.value) return {}
    const role = roles.value.find(r => r.name === currentUser.value!.role_name)
    return role?.permissions || {}
  })

  function hasPermission(resource: string, action: string): boolean {
    if (!currentUser.value) return false
    if (currentUser.value.role_name === 'admin') return true
    return currentUserPermissions.value[resource]?.[action] ?? false
  }

  async function login(username: string, password: string) {
    _loadingCount.value++
    try {
      const { data } = await userApi.login({ username, password })
      if (data.success && data.user) {
        currentUser.value = data.user
        isAuthenticated.value = true
        localStorage.setItem('xagent_user', JSON.stringify(data.user))
        try {
          await fetchRoles()
        } catch {
          // ignore
        }
        return true
      }
      return false
    } catch {
      return false
    } finally {
      _loadingCount.value--
    }
  }

  function logout() {
    currentUser.value = null
    isAuthenticated.value = false
    localStorage.removeItem('xagent_user')
  }

  function restoreSession() {
    const stored = localStorage.getItem('xagent_user')
    if (stored) {
      try {
        currentUser.value = JSON.parse(stored)
        isAuthenticated.value = true
        if (roles.value.length === 0) {
          fetchRoles().catch(() => {})
        }
      } catch {
        localStorage.removeItem('xagent_user')
      }
    }
  }

  async function fetchUsers() {
    _loadingCount.value++
    try {
      const { data } = await userApi.listUsers()
      users.value = data.users
    } catch {
      users.value = []
    } finally {
      _loadingCount.value--
    }
  }

  async function fetchRoles() {
    _loadingCount.value++
    try {
      const { data } = await userApi.listRoles()
      roles.value = data.roles
    } catch {
      roles.value = []
    } finally {
      _loadingCount.value--
    }
  }

  async function fetchPermissionMatrix() {
    _loadingCount.value++
    try {
      const { data } = await userApi.getPermissionMatrix()
      permissionMatrix.value = data
    } catch {
      permissionMatrix.value = null
    } finally {
      _loadingCount.value--
    }
  }

  async function createUser(userData: { username: string; password: string; role_name: string; display_name?: string; email?: string }) {
    const { data } = await userApi.createUser(userData)
    if (data.success) {
      await fetchUsers()
    }
    return data
  }

  async function updateUser(userId: number, userData: { display_name?: string; email?: string; role_name?: string; status?: string }) {
    const { data } = await userApi.updateUser(userId, userData)
    if (data.success) {
      await fetchUsers()
    }
    return data
  }

  async function deleteUser(userId: number) {
    const { data } = await userApi.deleteUser(userId)
    if (data.success) {
      await fetchUsers()
    }
    return data
  }

  async function createRole(roleData: { name: string; display_name: string; description?: string; permissions?: Record<string, Record<string, boolean>> }) {
    const { data } = await userApi.createRole(roleData)
    if (data.success) {
      await fetchRoles()
      await fetchPermissionMatrix()
    }
    return data
  }

  async function updateRole(roleName: string, roleData: { display_name?: string; description?: string; permissions?: Record<string, Record<string, boolean>> }) {
    const { data } = await userApi.updateRole(roleName, roleData)
    if (data.success) {
      await fetchRoles()
      await fetchPermissionMatrix()
    }
    return data
  }

  async function deleteRole(roleName: string) {
    const { data } = await userApi.deleteRole(roleName)
    if (data.success) {
      await fetchRoles()
      await fetchPermissionMatrix()
    }
    return data
  }

  async function updatePermissionMatrix(roleName: string, permissions: Record<string, Record<string, boolean>>) {
    const { data } = await userApi.updatePermissionMatrix(roleName, permissions)
    if (data.success) {
      await fetchPermissionMatrix()
    }
    return data
  }

  return {
    currentUser,
    users,
    roles,
    permissionMatrix,
    loading,
    isAuthenticated,
    isLoggedIn,
    currentUserPermissions,
    hasPermission,
    login,
    logout,
    restoreSession,
    fetchUsers,
    fetchRoles,
    fetchPermissionMatrix,
    createUser,
    updateUser,
    deleteUser,
    createRole,
    updateRole,
    deleteRole,
    updatePermissionMatrix,
  }
})
