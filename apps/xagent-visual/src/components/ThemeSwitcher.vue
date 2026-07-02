<template>
  <el-tooltip :content="isDark ? $t('layout.lightTheme') : $t('layout.darkTheme')" placement="bottom">
    <el-button
      :icon="isDark ? Sunny : Moon"
      circle
      size="small"
      @click="toggleTheme"
      class="theme-switcher-btn"
    />
  </el-tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Sunny, Moon } from '@element-plus/icons-vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

const isDark = computed(() => themeStore.theme === 'dark')

function toggleTheme() {
  themeStore.toggleTheme()
}
</script>

<style scoped>
.theme-switcher-btn {
  transition: var(--transition-fast);
}
</style>
