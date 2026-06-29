import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeMode>((localStorage.getItem('theme') as ThemeMode) || 'light')

  function setTheme(newTheme: ThemeMode) {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
    applyTheme(newTheme)
  }

  function toggleTheme() {
    const newTheme = theme.value === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
  }

  function applyTheme(mode: ThemeMode) {
    document.documentElement.setAttribute('data-theme', mode)
  }

  // 初始化时应用主题
  applyTheme(theme.value)

  return {
    theme,
    setTheme,
    toggleTheme,
    isDark: () => theme.value === 'dark'
  }
}, {
  persist: {
    key: 'xagent-theme',
    storage: localStorage,
    paths: ['theme']
  }
})
