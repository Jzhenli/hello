<template>
  <div 
    class="text-container"
    :style="{
      fontSize: `${textConfig?.fontSize || 14}px`,
      color: textConfig?.fontColor || '#2c3e50',
      fontWeight: textConfig?.fontWeight || 'normal',
      textAlign: textConfig?.textAlign || 'center'
    }"
  >
    {{ textConfig?.content || t('scadaComponents.defaultText') }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ScadaComponent } from '@/types/scada'

const { t } = useI18n()

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const textConfig = computed(() => props.config.textConfig)
</script>

<style scoped>
.text-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  word-break: break-word;
}
</style>
