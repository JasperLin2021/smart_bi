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
                <stop stop-color="#06b6d4"/>
                <stop offset="1" stop-color="#0891b2"/>
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
      
      <p class="login-footer">© 2026 Smart BI - Powered by AI</p>
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
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.login-bg-shape {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 20s infinite ease-in-out;
}

.login-bg-shape-1 {
  width: 400px;
  height: 400px;
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.login-bg-shape-2 {
  width: 300px;
  height: 300px;
  bottom: -50px;
  right: -50px;
  animation-delay: -5s;
}

.login-bg-shape-3 {
  width: 200px;
  height: 200px;
  top: 50%;
  left: 60%;
  animation-delay: -10s;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-30px) rotate(10deg); }
}

.login-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  padding: 20px;
}

.login-brand {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
}

.login-logo svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.15));
}

.login-title {
  color: white;
  font-size: 32px;
  font-weight: 700;
  margin: 0 0 8px 0;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.login-subtitle {
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  margin: 0;
}

.login-card {
  border-radius: 20px;
  border: none;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.login-card :deep(.el-card__body) {
  padding: 32px;
}

.login-form {
  margin-bottom: 0;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 12px;
  padding: 4px 16px;
}

.login-btn {
  width: 100%;
  border-radius: 12px;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  border: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(6, 182, 212, 0.4);
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
  transform: scale(1.05);
  background: #f3f4f6;
}

.login-footer {
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  margin-top: 24px;
}
</style>
