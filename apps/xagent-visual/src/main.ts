import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

/**
 * Wait for router to be ready before mounting the app.
 * 
 * This is critical for desktop app webview environment where initialization
 * may be slower than in regular browsers. It ensures:
 * 1. Router is fully initialized before any navigation
 * 2. Route guards are ready to handle authentication
 * 3. Menu components have correct active state
 * 
 * Without this, navigation may not work on first load in webview.
 */
router.isReady().then(() => {
  app.mount('#app')
})
