<script setup lang="ts">
defineProps<{
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}>()
</script>

<template>
  <div class="toast" :class="type">
    <span class="toast-icon">
      <template v-if="type === 'success'">✓</template>
      <template v-else-if="type === 'error'">✕</template>
      <template v-else-if="type === 'warning'">⚠</template>
      <template v-else>ℹ</template>
    </span>
    <span class="toast-message">{{ message }}</span>
  </div>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.toast.success {
  background: #27ae60;
  color: #fff;
}

.toast.error {
  background: #e74c3c;
  color: #fff;
}

.toast.warning {
  background: #f39c12;
  color: #fff;
}

.toast.info {
  background: #3498db;
  color: #fff;
}

.toast-icon {
  font-size: 16px;
  font-weight: bold;
}

.toast-message {
  font-size: 14px;
}
</style>
