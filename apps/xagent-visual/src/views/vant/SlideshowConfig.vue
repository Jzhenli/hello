<template>
  <el-dialog
    v-model="visible"
    :title="$t('scada.slideshowConfig')"
    width="480px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form label-width="120px">
      <el-form-item :label="$t('scada.slideshowInterval')">
        <el-input-number
          v-model="config.interval"
          :min="1"
          :max="60"
          :step="1"
          :placeholder="$t('scada.slideshowInterval')"
        />
        <span class="unit-label">{{ $t('scada.slideshowIntervalUnit') }}</span>
      </el-form-item>
      <el-form-item :label="$t('scada.slideshowLoop')">
        <el-switch v-model="config.loop" />
      </el-form-item>
      <el-form-item :label="$t('scada.slideshowAutoPlay')">
        <el-switch v-model="config.autoPlay" />
      </el-form-item>
      <el-form-item :label="$t('scada.slideshowTransition')">
        <el-select v-model="config.transition">
          <el-option :label="$t('scada.slideshowTransitionFade')" value="fade" />
          <el-option :label="$t('scada.slideshowTransitionSlide')" value="slide" />
          <el-option :label="$t('scada.slideshowTransitionNone')" value="none" />
        </el-select>
      </el-form-item>
      <el-form-item :label="$t('scada.slideshowProjectScope')">
        <el-select v-model="config.scope">
          <el-option :label="$t('scada.slideshowScopeAll')" value="all" />
          <el-option :label="$t('scada.slideshowScopeDashboard')" value="Dashboard" />
          <el-option :label="$t('scada.slideshowScopeGraphic')" value="Graphic" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">{{ $t('common.cancel') }}</el-button>
      <el-button type="primary" @click="handleStart">{{ $t('scada.slideshowStart') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

export interface SlideshowConfig {
  interval: number
  loop: boolean
  autoPlay: boolean
  transition: 'fade' | 'slide' | 'none'
  scope: 'all' | 'Dashboard' | 'Graphic'
}

const props = defineProps<{
  modelValue: boolean
  initialConfig?: Partial<SlideshowConfig>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'start', config: SlideshowConfig): void
}>()

const defaultConfig: SlideshowConfig = {
  interval: 5,
  loop: true,
  autoPlay: true,
  transition: 'fade',
  scope: 'all',
}

const config = ref<SlideshowConfig>({ ...defaultConfig, ...props.initialConfig })

const visible = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    config.value = { ...defaultConfig, ...props.initialConfig }
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

const handleClose = () => {
  visible.value = false
}

const handleStart = () => {
  emit('start', { ...config.value })
  visible.value = false
}
</script>

<style scoped>
.unit-label {
  margin-left: 8px;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
