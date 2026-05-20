<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  Odometer, 
  Monitor, 
  Connection, 
  Bell, 
  Setting,
  User,
  PictureFilled,
  Expand,
  Fold,
  Menu
} from '@element-plus/icons-vue'
import { useAlertStore } from '@/stores/alerts'
import { useScadaStore } from '@/stores/scada'
import { useResponsive } from '@/utils/useResponsive'

const route = useRoute()
const router = useRouter()
const alertStore = useAlertStore()
const scadaStore = useScadaStore()
const { isTablet, isMobile, isTouch } = useResponsive()

const isCollapsed = ref(false)
const isDrawerVisible = ref(false)

const menuItems = [
  { path: '/dashboard', title: '监控面板', icon: Odometer },
  { path: '/devices', title: '设备管理', icon: Monitor },
  { path: '/rules', title: '规则编辑', icon: Connection },
  { path: '/alerts', title: '告警配置', icon: Bell },
  { path: '/scada', title: '组态面板', icon: PictureFilled },
  { path: '/settings', title: '系统设置', icon: Setting }
]

const activeMenu = computed(() => route.path)

const handleMenuSelect = (path: string) => {
  router.push(path)
  if (isTablet.value || isMobile.value) {
    isDrawerVisible.value = false
  }
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleDrawer = () => {
  isDrawerVisible.value = !isDrawerVisible.value
}

const isFullscreenMode = computed(() => scadaStore.isFullscreenPreview)

const showSidebar = computed(() => !isTablet.value && !isMobile.value)
const showDrawer = computed(() => isTablet.value || isMobile.value)
</script>

<template>
  <el-container class="app-layout">
    <template v-if="showSidebar">
      <el-aside 
        :width="isCollapsed ? '64px' : '220px'" 
        class="app-aside"
        :class="{ collapsed: isCollapsed, 'fullscreen-hidden': isFullscreenMode }"
      >
        <div class="logo">
          <span class="logo-icon">⚡</span>
          <span v-if="!isCollapsed" class="logo-text">XAgent</span>
        </div>
        
        <el-menu
          :default-active="activeMenu"
          class="app-menu"
          :collapse="isCollapsed"
          @select="handleMenuSelect"
        >
          <el-menu-item 
            v-for="item in menuItems" 
            :key="item.path" 
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
            <el-badge 
              v-if="item.path === '/alerts' && alertStore.pendingAlerts > 0"
              :value="alertStore.pendingAlerts" 
              class="menu-badge"
            />
          </el-menu-item>
        </el-menu>
        
        <div class="aside-footer">
          <el-button 
            class="collapse-btn"
            :icon="isCollapsed ? Expand : Fold"
            @click="toggleCollapse"
            text
          />
          <div v-if="!isCollapsed" class="version">v1.0.0</div>
        </div>
      </el-aside>
    </template>

    <el-drawer
      v-if="showDrawer"
      v-model="isDrawerVisible"
      direction="ltr"
      :with-header="false"
      size="260px"
      class="mobile-drawer"
      :class="{ 'fullscreen-hidden': isFullscreenMode }"
    >
      <div class="drawer-content">
        <div class="logo">
          <span class="logo-icon">⚡</span>
          <span class="logo-text">XAgent</span>
        </div>
        
        <el-menu
          :default-active="activeMenu"
          class="app-menu mobile-menu"
          @select="handleMenuSelect"
        >
          <el-menu-item 
            v-for="item in menuItems" 
            :key="item.path" 
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
            <el-badge 
              v-if="item.path === '/alerts' && alertStore.pendingAlerts > 0"
              :value="alertStore.pendingAlerts" 
              class="menu-badge"
            />
          </el-menu-item>
        </el-menu>
        
        <div class="drawer-footer">
          <div class="version">v1.0.0</div>
        </div>
      </div>
    </el-drawer>

    <el-container :class="{ 'fullscreen-mode': isFullscreenMode }">
      <el-header v-if="!isFullscreenMode" class="app-header" :class="{ 'mobile-header': isMobile || isTablet }">
        <div class="header-left">
          <el-button 
            v-if="showDrawer"
            :icon="Menu"
            class="menu-toggle-btn"
            @click="toggleDrawer"
          />
          <span class="page-title">{{ route.meta.title }}</span>
        </div>
        <div class="header-right">
          <el-badge :value="alertStore.pendingAlerts" :hidden="alertStore.pendingAlerts === 0">
            <el-button :icon="Bell" circle />
          </el-badge>
          <el-dropdown>
            <el-avatar :size="32" class="user-avatar">
              <el-icon><User /></el-icon>
            </el-avatar>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人设置</el-dropdown-item>
                <el-dropdown-item divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="app-main" :class="{ 'fullscreen-main': isFullscreenMode }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
      
      <el-footer v-if="!isFullscreenMode && !isMobile" class="app-footer" height="32px">
        <span>设备在线 12/15</span>
        <span class="divider">|</span>
        <span>规则执行 156 次/今日</span>
        <span class="divider">|</span>
        <span class="status-ok">系统正常</span>
      </el-footer>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
  overflow: hidden;
}

.app-aside {
  background: linear-gradient(180deg, #1e3a5f 0%, #0d1b2a 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.app-aside.collapsed .logo {
  justify-content: center;
}

.app-aside.fullscreen-hidden {
  width: 0 !important;
  overflow: hidden;
  opacity: 0;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 1px;
}

.app-menu {
  flex: 1;
  border-right: none;
  background: transparent;
}

.app-menu .el-menu-item {
  color: rgba(255, 255, 255, 0.7);
  height: 50px;
  line-height: 50px;
  margin: 4px 8px;
  border-radius: 8px;
}

.app-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.app-menu .el-menu-item.is-active {
  background: linear-gradient(90deg, #3498db, #2980b9);
  color: #fff;
}

.mobile-menu .el-menu-item {
  height: 56px;
  line-height: 56px;
  font-size: 16px;
}

.menu-badge {
  margin-left: auto;
}

.aside-footer {
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.collapse-btn {
  color: rgba(255, 255, 255, 0.7);
}

.collapse-btn:hover {
  color: #fff;
}

.version {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  text-align: center;
}

.mobile-drawer.fullscreen-hidden {
  display: none;
}

.drawer-content {
  height: 100%;
  background: linear-gradient(180deg, #1e3a5f 0%, #0d1b2a 100%);
  display: flex;
  flex-direction: column;
}

.drawer-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.app-header.mobile-header {
  padding: 0 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-toggle-btn {
  font-size: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #2c3e50;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-avatar {
  cursor: pointer;
  background: #3498db;
}

.app-main {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}

.app-main.fullscreen-main {
  padding: 0;
}

.fullscreen-mode {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
}

.app-footer {
  background: #fff;
  border-top: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  color: #7f8c8d;
}

.divider {
  color: #ddd;
}

.status-ok {
  color: #27ae60;
  font-weight: 500;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 1024px) {
  .app-main {
    padding: 12px;
  }
  
  .page-title {
    font-size: 16px;
  }
  
  .header-right {
    gap: 8px;
  }
}

@media (max-width: 768px) {
  .app-main {
    padding: 8px;
  }
  
  .page-title {
    font-size: 14px;
  }
}
</style>
