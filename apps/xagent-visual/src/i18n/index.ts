import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'

const defaultLocale = localStorage.getItem('locale') || 'zh-CN'

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: defaultLocale,
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en': en,
    'zh-TW': zhTW
  }
})

export default i18n
