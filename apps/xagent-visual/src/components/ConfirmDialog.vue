<template>
  <div class="confirm-overlay" @click.self="emit('cancel')">
    <div class="confirm-dialog">
      <div class="confirm-icon">⚠️</div>
      <div class="confirm-message">{{ message }}</div>
      <div class="confirm-buttons">
        <button class="btn-cancel" @click="emit('cancel')">{{ t('confirmDialog.cancel') }}</button>
        <button class="btn-ok" @click="emit('ok')">{{ t('confirmDialog.confirm') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  message: string
}>()

const emit = defineEmits<{
  (e: 'ok'): void
  (e: 'cancel'): void
}>()
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--confirm-overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.confirm-dialog {
  background: var(--confirm-dialog-bg);
  border-radius: 12px;
  padding: 24px;
  min-width: 320px;
  max-width: 400px;
  box-shadow: var(--confirm-dialog-shadow);
  text-align: center;
}

.confirm-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.confirm-message {
  font-size: 16px;
  color: var(--confirm-message-color);
  margin-bottom: 24px;
  line-height: 1.5;
}

.confirm-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-cancel,
.btn-ok {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-cancel {
  background: var(--confirm-cancel-bg);
  color: var(--confirm-cancel-color);
}

.btn-cancel:hover {
  background: var(--confirm-cancel-hover-bg);
}

.btn-ok {
  background: var(--confirm-ok-bg);
  color: var(--confirm-ok-color);
}

.btn-ok:hover {
  background: var(--confirm-ok-hover-bg);
}
</style>
