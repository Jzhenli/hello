<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/users'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginForm = ref({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const success = await userStore.login(loginForm.value.username, loginForm.value.password)
    if (success) {
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/dashboard'
      router.push(redirect)
    } else {
      ElMessage.error('用户名或密码错误')
    }
  } catch {
    ElMessage.error('登录失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="bg-pattern"></div>
    </div>
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <div class="login-logo">
            <span class="logo-icon">⚡</span>
          </div>
          <h1 class="login-title">XAgent</h1>
          <p class="login-subtitle">IoT 网关控制台</p>
        </div>
        <el-form class="login-form" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              v-model="loginForm.username"
              placeholder="用户名"
              size="large"
              prefix-icon="User"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码"
              size="large"
              prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>
        <div class="login-footer">
          <span>XAgent IoT Gateway v1.0</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
  padding: 16px;
}

.login-bg {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #0d1b2a 0%, #1e3a5f 50%, #2c5f8a 100%);
  z-index: 0;
}

.bg-pattern {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 20% 50%, rgba(52, 152, 219, 0.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(41, 128, 185, 0.1) 0%, transparent 40%),
    radial-gradient(circle at 60% 80%, rgba(52, 152, 219, 0.08) 0%, transparent 45%);
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
}

.login-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  padding: clamp(24px, 5vw, 40px) clamp(20px, 4vw, 36px) clamp(20px, 3vw, 32px);
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.3),
    0 0 0 1px rgba(255, 255, 255, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: clamp(16px, 4vw, 32px);
}

.login-logo {
  margin-bottom: clamp(8px, 2vw, 16px);
}

.logo-icon {
  font-size: clamp(32px, 8vw, 48px);
  display: inline-block;
}

.login-title {
  font-size: clamp(22px, 5vw, 28px);
  font-weight: 700;
  color: #1e3a5f;
  margin: 0 0 4px 0;
  letter-spacing: 2px;
}

.login-subtitle {
  font-size: clamp(12px, 3vw, 14px);
  color: #7f8c8d;
  margin: 0;
}

.login-form {
  margin-bottom: clamp(8px, 2vw, 16px);
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.login-btn {
  width: 100%;
  border-radius: 8px;
  font-size: clamp(14px, 3vw, 16px);
  letter-spacing: 4px;
}

.login-footer {
  text-align: center;
  color: #bdc3c7;
  font-size: 12px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

@media (max-height: 500px) {
  .login-header {
    margin-bottom: 12px;
  }
  .login-logo {
    margin-bottom: 4px;
  }
  .login-card {
    padding: 16px 20px;
  }
}
</style>
