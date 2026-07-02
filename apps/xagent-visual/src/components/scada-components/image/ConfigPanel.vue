<template>
  <div class="config-section">
    <div class="section-title">{{ t('componentConfig.imageConfig') }}</div>
    <div class="form-group">
      <label>{{ t('componentConfig.imageSource') }}</label>
      <div v-if="component.imageConfig?.url" class="bg-image-card">
        <div class="bg-image-preview">
          <img :src="component.imageConfig.url" alt="image">
        </div>
        <div class="bg-image-actions">
          <el-button size="small" @click="triggerImageUpload">{{ t('componentConfig.changeImage') }}</el-button>
          <el-button size="small" type="danger" @click="removeImage">{{ t('componentConfig.removeImage') }}</el-button>
        </div>
      </div>
      <div v-else class="bg-upload-area" @click="triggerImageUpload">
        <span class="upload-icon">+</span>
        <span class="upload-text">{{ t('componentConfig.uploadImage') }}</span>
      </div>
      <input 
        ref="imageFileInput"
        type="file"
        accept="image/*"
        class="hidden-file-input"
        @change="handleImageUpload"
      />
    </div>
    <div class="form-group">
      <label>{{ t('componentConfig.imageFit') }}</label>
      <select :value="component.imageConfig?.fit || 'contain'" @change="updateConfig('fit', ($event.target as HTMLSelectElement).value)">
        <option value="contain">{{ t('componentConfig.fitContain') }}</option>
        <option value="cover">{{ t('componentConfig.fitCover') }}</option>
        <option value="fill">{{ t('componentConfig.fitFill') }}</option>
      </select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import type { ScadaComponent } from '@/types/scada'

const { t } = useI18n()
const scadaStore = useScadaStore()

const props = defineProps<{
  component: ScadaComponent
}>()

const imageFileInput = ref<HTMLInputElement | null>(null)

const updateConfig = (key: string, value: any) => {
  const config = props.component.imageConfig || {}
  scadaStore.updateComponent(props.component.id, {
    imageConfig: { ...config, [key]: value }
  })
}

const handleImageUpload = (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (event) => {
    const result = event.target?.result as string
    if (result) {
      updateConfig('url', result)
    }
  }
  reader.readAsDataURL(file)
  
  input.value = ''
}

const removeImage = () => {
  updateConfig('url', undefined)
}

const triggerImageUpload = () => {
  imageFileInput.value?.click()
}
</script>

<style scoped>
.config-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}

.config-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.hidden-file-input {
  display: none;
}

.form-group select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  font-size: 13px;
}

.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.bg-image-card {
  border: 1px solid var(--border-base);
  border-radius: 6px;
  overflow: hidden;
}

.bg-image-preview {
  width: 100%;
  height: 100px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.bg-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bg-image-actions {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: var(--bg-container);
}

.bg-image-actions .el-button {
  flex: 1;
}

.bg-upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100px;
  border: 2px dashed var(--border-base);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.bg-upload-area:hover {
  border-color: var(--color-primary);
  background: rgba(64, 158, 255, 0.05);
}

.upload-icon {
  font-size: 32px;
  color: var(--text-secondary);
  line-height: 1;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>