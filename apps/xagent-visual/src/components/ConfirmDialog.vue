<script setup lang="ts">
defineProps<{
  message: string
}>()

const emit = defineEmits<{
  (e: 'ok'): void
  (e: 'cancel'): void
}>()
</script>

<template>
  <div class="confirm-overlay" @click.self="emit('cancel')">
    <div class="confirm-dialog">
      <div class="confirm-icon">⚠️</div>
      <div class="confirm-message">{{ message }}</div>
      <div class="confirm-buttons">
        <button class="btn-cancel" @click="emit('cancel')">取消</button>
        <button class="btn-ok" @click="emit('ok')">确定</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.confirm-dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  min-width: 320px;
  max-width: 400px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  text-align: center;
}

.confirm-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.confirm-message {
  font-size: 16px;
  color: #2c3e50;
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
  background: #f5f7fa;
  color: #606266;
}

.btn-cancel:hover {
  background: #e4e7ed;
}

.btn-ok {
  background: #e74c3c;
  color: #fff;
}

.btn-ok:hover {
  background: #c0392b;
}
</style>
