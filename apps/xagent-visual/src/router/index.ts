import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/users'

const ROUTE_PERMISSION_MAP: Record<string, string> = {
  '/dashboard': 'dashboard',
  '/devices': 'devices',
  '/channels': 'channels',
  '/rules': 'rules',
  '/alerts': 'alerts',
  '/scada': 'scada',
  '/settings': 'settings',
}

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '监控面板', icon: 'Odometer' }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/Devices.vue'),
    meta: { title: '设备管理', icon: 'Monitor' }
  },
  {
    path: '/channels',
    name: 'NorthChannels',
    component: () => import('@/views/NorthChannels.vue'),
    meta: { title: '通道管理', icon: 'Connection' }
  },
  {
    path: '/rules',
    name: 'Rules',
    component: () => import('@/views/Rules.vue'),
    meta: { title: '规则引擎', icon: 'Connection' }
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('@/views/Alerts.vue'),
    meta: { title: '告警配置', icon: 'Bell' }
  },
  {
    path: '/scada',
    name: 'Scada',
    component: () => import('@/views/Scada.vue'),
    meta: { title: '组态面板', icon: 'PictureFilled' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '系统设置', icon: 'Setting' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

function findFirstAllowedPath(userStore: ReturnType<typeof useUserStore>): string {
  const paths = ['/dashboard', '/devices', '/channels', '/rules', '/alerts', '/scada', '/settings']
  for (const p of paths) {
    const resource = ROUTE_PERMISSION_MAP[p]
    if (!resource || userStore.hasPermission(resource, 'view')) {
      return p
    }
  }
  return '/dashboard'
}

router.beforeEach(async (to, _from, next) => {
  document.title = `${to.meta.title || 'XAgent'} - XAgent 控制台`

  if (to.meta.public) {
    next()
    return
  }

  const userStore = useUserStore()
  
  // Restore session from localStorage if not already authenticated
  if (!userStore.isLoggedIn) {
    userStore.restoreSession()
  }

  if (!userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // Fetch roles if not already loaded
  if (userStore.roles.length === 0) {
    try {
      await userStore.fetchRoles()
    } catch (error) {
      console.error('Failed to fetch roles:', error)
      // Continue even if roles fetch fails - user can still navigate
    }
  }

  const resource = ROUTE_PERMISSION_MAP[to.path]
  if (resource && !userStore.hasPermission(resource, 'view')) {
    const allowed = findFirstAllowedPath(userStore)
    if (allowed === to.path) {
      next()
    } else {
      next(allowed)
    }
    return
  }

  next()
})

export default router
export { ROUTE_PERMISSION_MAP }
