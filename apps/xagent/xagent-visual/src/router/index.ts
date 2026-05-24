import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'XAgent'} - XAgent 控制台`
  next()
})

export default router
