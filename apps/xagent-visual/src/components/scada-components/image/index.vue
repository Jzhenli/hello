<template>
  <div class="image-container">
    <div v-if="!imageUrl && editing" class="image-placeholder">
      <span>图片</span>
    </div>
    <img
      v-else
      :src="imageUrl"
      :alt="config.name"
      class="image-content"
      :style="imageStyle"
      draggable="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScadaComponent } from '@/types/scada'

const props = defineProps<{
  config: ScadaComponent
  editing?: boolean
}>()

const imageUrl = computed(() => props.config.imageConfig?.url || '')
const objectFit = computed(() => props.config.imageConfig?.fit || 'contain')
const imageStyle = computed(() => `object-fit: ${objectFit.value};`)
</script>

<style scoped>
.image-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-container);
  border-radius: 4px;
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--text-placeholder);
  font-size: 14px;
  border: 2px dashed var(--border-base);
  border-radius: 4px;
}

.image-content {
  width: 100%;
  height: 100%;
  display: block;
}
</style>