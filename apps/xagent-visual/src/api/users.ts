import api from './index'

export interface UserInfo {
  id: number
  username: string
  display_name: string | null
  email: string | null
  role_name: string
  role_display_name: string | null
  status: string
  last_login: number | null
  created_at: number
  updated_at: number
}

export interface UserListResponse {
  count: number
  users: UserInfo[]
}

export interface UserCreateRequest {
  username: string
  password: string
  role_name: string
  display_name?: string
  email?: string
}

export interface UserUpdateRequest {
  display_name?: string
  email?: string
  role_name?: string
  status?: string
}

export interface RoleInfo {
  id: number
  name: string
  display_name: string
  description: string | null
  permissions: Record<string, Record<string, boolean>>
  is_system: boolean
  created_at: number
  updated_at: number
}

export interface RoleListResponse {
  count: number
  roles: RoleInfo[]
}

export interface RoleCreateRequest {
  name: string
  display_name: string
  description?: string
  permissions?: Record<string, Record<string, boolean>>
}

export interface RoleUpdateRequest {
  display_name?: string
  description?: string
  permissions?: Record<string, Record<string, boolean>>
}

export interface PermissionMatrix {
  resources: string[]
  actions: string[]
  roles: {
    name: string
    display_name: string
    is_system: boolean
    permissions: Record<string, Record<string, boolean>>
  }[]
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  success: boolean
  message: string
  user: UserInfo | null
}

export const userApi = {
  login(data: LoginRequest) {
    return api.post<LoginResponse>('/api/users/login', data)
  },

  listUsers() {
    return api.get<UserListResponse>('/api/users/list')
  },

  getUser(userId: number) {
    return api.get<UserInfo>(`/api/users/${userId}`)
  },

  createUser(data: UserCreateRequest) {
    return api.post<{ success: boolean; message: string; user: UserInfo }>('/api/users/create', data)
  },

  updateUser(userId: number, data: UserUpdateRequest) {
    return api.put<{ success: boolean; message: string; user: UserInfo }>(`/api/users/${userId}`, data)
  },

  deleteUser(userId: number) {
    return api.delete<{ success: boolean; message: string }>(`/api/users/${userId}`)
  },

  changePassword(userId: number, newPassword: string) {
    return api.put<{ success: boolean; message: string }>(`/api/users/${userId}/password`, { new_password: newPassword })
  },

  listRoles() {
    return api.get<RoleListResponse>('/api/users/roles/list')
  },

  getRole(roleName: string) {
    return api.get<RoleInfo>(`/api/users/roles/${roleName}`)
  },

  createRole(data: RoleCreateRequest) {
    return api.post<{ success: boolean; message: string; role: RoleInfo }>('/api/users/roles/create', data)
  },

  updateRole(roleName: string, data: RoleUpdateRequest) {
    return api.put<{ success: boolean; message: string; role: RoleInfo }>(`/api/users/roles/${roleName}`, data)
  },

  deleteRole(roleName: string) {
    return api.delete<{ success: boolean; message: string }>(`/api/users/roles/${roleName}`)
  },

  getPermissionMatrix() {
    return api.get<PermissionMatrix>('/api/users/permissions/matrix')
  },

  updatePermissionMatrix(roleName: string, permissions: Record<string, Record<string, boolean>>) {
    return api.put<{ success: boolean; message: string }>('/api/users/permissions/matrix', {
      role_name: roleName,
      permissions,
    })
  },

  checkPermission(username: string, resource: string, action: string) {
    return api.get<{ username: string; resource: string; action: string; allowed: boolean }>('/api/users/permissions/check', {
      params: { username, resource, action },
    })
  },

  getUserPermissions(username: string) {
    return api.get<{ username: string; permissions: Record<string, Record<string, boolean>> }>(`/api/users/${username}/permissions`)
  },
}
