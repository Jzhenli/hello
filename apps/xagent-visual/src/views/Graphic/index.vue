<template>
  <div class="graphic-editor-container">
    <GraphicEditor
      class="graphic-editor"
      v-if="graphicData !== null && showEditor"
      :graphicData="graphicData"
      @onExit="onExit()"
      @onSave="onSave"
      @showPreview="showPreview"
    ></GraphicEditor>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { GraphicEditor } from "@x-plateform/graphic-editor";
import { onMounted, ref, watch, nextTick, computed } from "vue";
import { useThemeStore } from '@/stores/theme'

declare global {
  interface Window {
    graphicItemManager: any
  }
  
  type Recordable<T = any> = Record<string, T>
}

//const route = useRoute();
const router = useRouter();
const { locale } = useI18n();
const themeStore = useThemeStore()

const isDark = computed(() => themeStore.theme === 'dark')

const graphicData = ref<any | null>(null);
const showEditor = ref(true);

onMounted(() => {
  graphicData.value = JSON.parse("{}");

  setLang()
  setTheme()
});

watch(locale, async () => {
  await nextTick()
  setLang()
});

//添加监听主题变化
watch(isDark, async () => {
  await nextTick()
  setTheme()
})

const setTheme = () => {
  const body = document.body

  if (isDark.value) {
    body.classList.remove('x-theme-2')
    body.classList.add('x-theme-1')
  } else {
    body.classList.remove('x-theme-1')
    body.classList.add('x-theme-2')
  }
}

const setLang = () => {
  const langMap: Record<string, string> = {
    'zh-CN': 'zh-CN',
    'zh-TW': 'zh-TW',
    'en': 'en-US'
  }
  const targetLang = langMap[locale.value] || 'zh-CN'
  
  // 先隐藏编辑器
  showEditor.value = false
  
  // 调用语言切换
  if (window.graphicItemManager) {
    window.graphicItemManager.switchLanguage(targetLang)
  }
  
  // 短暂延迟后重新显示，触发完全重建
  setTimeout(() => {
    showEditor.value = true
  }, 50)
}

const onExit = () => {
  router.push({ name: "ScadaList" });
};

const onSave = (data: any, callback?: (success: boolean) => void) => {
  console.log(data, callback)

  //add
};

const showPreview = () => {};
</script>

<style scoped>
.graphic-editor-container {
  height: calc(100vh - 100px - 32px);
  display: flex;
  flex-direction: column;
  /* background-color: var(--bg-secondary); */
}
</style>
