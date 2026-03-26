<template>
  <el-row justify="center" align="middle" class="login-page">
    <el-col :xs="22" :sm="12" :md="8" :lg="6">
      <el-card class="login-card">
        <template #header>
          <div class="login-header">登录系统</div>
        </template>
        <el-form :model="form" @submit.prevent>
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="密码" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="submit" class="full-width">
              登录
            </el-button>
          </el-form-item>
          <el-alert
            title="默认账号：admin / admin123"
            type="info"
            show-icon
            :closable="false"
          />
        </el-form>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/store/auth"

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({ username: "", password: "" })

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
