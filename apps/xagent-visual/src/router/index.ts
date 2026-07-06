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

// Match routes with dynamic segments
function matchRoute(path: string): string | null {
  if (ROUTE_PERMISSION_MAP[path]) {
    return ROUTE_PERMISSION_MAP[path]
  }
  // Handle /scada/:id/preview
  if (path.startsWith('/scada/') && path.endsWith('/preview')) {
    return ROUTE_PERMISSION_MAP['/scada']
  }
  // Handle /scada/:id
  if (path.startsWith('/scada/')) {
    return ROUTE_PERMISSION_MAP['/scada']
  }
  // Handle /graphic/:id/preview
  if (path.startsWith('/graphic/') && path.endsWith('/preview')) {
    return ROUTE_PERMISSION_MAP['/scada']
  }
  // Handle /graphic/:id
  if (path.startsWith('/graphic/')) {
    return ROUTE_PERMISSION_MAP['/scada']
  }
  return null
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
    name: 'ScadaList',
    component: () => import('@/views/ProjectList/index.vue'),
    meta: { title: '项目管理', icon: 'Folder' }
  },
  {
    path: '/scada/slideshow',
    name: 'SlideshowPreview',
    component: () => import('@/views/vant/SlideshowPreview.vue'),
    meta: { title: '幻灯片预览', icon: 'PictureFilled', public: true }
  },
  {
    path: '/scada/:id',
    name: 'ScadaEdit',
    component: () => import('@/views/Scada.vue'),
    meta: { title: '组态编辑', icon: 'PictureFilled' }
  },
  {
    path: '/scada/:id/preview',
    name: 'ScadaPreview',
    component: () => import('@/views/ScadaPreview.vue'),
    meta: { title: '组态预览', icon: 'PictureFilled', public: true }
  },
  {
    path: '/graphic/:id',
    name: 'GraphicEdit',
    component: () => import('@/views/Graphic/index.vue'),
    meta: { title: '图形编辑', icon: 'PictureFilled' }
  },
  {
    path: '/graphic/:id/preview',
    name: 'GraphicPreview',
    component: () => import('@/views/GraphicPreview/index.vue'),
    meta: { title: '图形预览', icon: 'PictureFilled', public: true }
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

  const resource = matchRoute(to.path)
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
