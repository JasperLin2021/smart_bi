<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :xs="24" :md="16">
        <el-card>
        <template #header>
          <div class="card-header">
            <span class="card-header-title">大模型配置</span>
            <el-button size="small" @click="loadConfig">刷新</el-button>
          </div>
        </template>
        <el-form label-width="120px" class="page-stack">
          <el-form-item label="提供商">
            <el-select v-model="form.provider" class="field-medium">
              <el-option label="OpenAI" value="openai" />
              <el-option label="Moonshot" value="moonshot" />
              <el-option label="Deepseek" value="deepseek" />
              <el-option label="Gemini" value="gemini" />
              <el-option label="自定义" value="custom" />
            </el-select>
            <el-button class="inline-button" @click="applyPreset">
              使用推荐
            </el-button>
          </el-form-item>
          <el-form-item label="API Base">
            <el-input v-model="form.base_url" placeholder="https://..." />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.model" placeholder="例如 gpt-4o-mini" />
          </el-form-item>
          <el-form-item label="温度">
            <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="form.api_key"
              type="password"
              :placeholder="apiKeyPlaceholder"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveConfig">
              保存配置
            </el-button>
          </el-form-item>
        </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card>
        <template #header>
          <span class="card-header-title">说明</span>
        </template>
        <el-space direction="vertical" alignment="start" class="info-card">
          <div>仅管理员可修改配置</div>
          <div>API Key 留空表示保持原值</div>
        </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import { useAuthStore } from "@/store/auth"
import { useRouter } from "vue-router"

const saving = ref(false)
const apiKeySet = ref(false)
const authStore = useAuthStore()
const router = useRouter()

const form = reactive({
  provider: "custom",
  base_url: "",
  model: "",
  temperature: 0.3,
  api_key: ""
})

const presets: Record<string, { base_url: string; model: string }> = {
  openai: { base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  moonshot: { base_url: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  deepseek: { base_url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  gemini: {
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    model: "gemini-1.5-flash"
  },
  custom: { base_url: "", model: "" }
}

const apiKeyPlaceholder = computed(() =>
  apiKeySet.value ? "已设置，留空则保持" : "请输入 API Key"
)

const applyPreset = () => {
  const preset = presets[form.provider]
  if (preset) {
    form.base_url = preset.base_url
    form.model = preset.model
  }
}

const loadConfig = async () => {
  const response = await axios.get("/api/settings/llm")
  form.provider = response.data.provider
  form.base_url = response.data.base_url
  form.model = response.data.model
  form.temperature = response.data.temperature
  form.api_key = ""
  apiKeySet.value = response.data.api_key_set
}

const saveConfig = async () => {
  saving.value = true
  try {
    await axios.put("/api/settings/llm", { ...form })
    ElMessage.success("配置已保存")
    await loadConfig()
  } catch (error) {
    ElMessage.error("保存失败")
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    await authStore.fetchProfile()
  }
  if (authStore.profile && authStore.profile.role !== "admin") {
    router.push("/dashboard")
    return
  }
  loadConfig()
})
</script>
