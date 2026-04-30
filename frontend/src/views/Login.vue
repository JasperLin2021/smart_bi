<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="login-bg-shape login-bg-shape-1"></div>
      <div class="login-bg-shape login-bg-shape-2"></div>
      <div class="login-bg-shape login-bg-shape-3"></div>
    </div>
    <div class="login-container">
      <div class="login-brand">
        <div class="login-logo">
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="40" height="40" rx="10" fill="url(#logo-gradient)"/>
            <path d="M12 28V12h4v16h-4zm6-8V12h4v8h-4zm6 4V12h4v12h-4z" fill="white"/>
            <defs>
              <linearGradient id="logo-gradient" x1="0" y1="0" x2="40" y2="40">
                <stop stop-color="#0f766e"/>
                <stop offset="1" stop-color="#2563eb"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <h1 class="login-title">Smart BI</h1>
        <p class="login-subtitle">智能商业分析平台</p>
      </div>
      
      <el-card class="login-card" shadow="always">
        <el-form :model="form" @submit.prevent class="login-form">
          <el-form-item>
            <el-input 
              v-model="form.username" 
              placeholder="用户名" 
              size="large"
              prefix-icon="User"
            />
          </el-form-item>
          <el-form-item>
            <el-input 
              v-model="form.password" 
              type="password" 
              placeholder="密码" 
              size="large"
              prefix-icon="Lock"
              show-password
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-form-item>
            <el-button 
              type="primary" 
              :loading="loading" 
              @click="submit" 
              class="login-btn"
              size="large"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>
        
        <div class="login-hint">
          <el-divider>
            <span class="hint-text">测试账号</span>
          </el-divider>
          <div class="account-chips">
            <el-tag @click="fillAccount('admin', 'admin123')" effect="plain" class="account-chip">
              超级管理员
            </el-tag>
            <el-tag @click="fillAccount('carsem_admin', 'carsem123')" effect="plain" class="account-chip">
              企业管理员
            </el-tag>
            <el-tag @click="fillAccount('carsem', 'carsem123')" effect="plain" class="account-chip">
              普通用户
            </el-tag>
          </div>
        </div>
      </el-card>
      
      <p class="login-footer">© 2026 Smart BI - Powered by Chinatelecom</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/store/auth"

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({ username: "", password: "" })

const fillAccount = (username: string, password: string) => {
  form.username = username
  form.password = password
}

const submit = async () => {
  if (!form.username || !form.password) return
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    await router.push("/dashboard")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(180deg, rgba(15, 118, 110, 0.06), transparent 38%),
    var(--app-bg);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.login-bg-shape {
  display: none;
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 20px;
}

.login-brand {
  text-align: center;
  margin-bottom: 24px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
}

.login-logo svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 8px 16px rgba(15, 118, 110, 0.14));
}

.login-title {
  color: var(--app-text);
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 8px 0;
}

.login-subtitle {
  color: var(--app-text-muted);
  font-size: 14px;
  margin: 0;
}

.login-card {
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow);
}

.login-card :deep(.el-card__body) {
  padding: 32px;
}

.login-form {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: var(--app-radius-sm);
  padding: 4px 16px;
}

.login-btn {
  width: 100%;
  border-radius: var(--app-radius-sm);
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  transition: transform 0.2s, box-shadow 0.2s;
}

.login-btn:hover {
  transform: none;
  box-shadow: none;
}

.login-hint {
  margin-top: 24px;
}

.hint-text {
  color: #9ca3af;
  font-size: 12px;
}

.account-chips {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.account-chip {
  cursor: pointer;
  transition: all 0.2s;
}

.account-chip:hover {
  transform: none;
  background: var(--app-surface-muted);
}

.login-footer {
  text-align: center;
  color: var(--app-text-light);
  font-size: 12px;
  margin-top: 24px;
}
</style>
