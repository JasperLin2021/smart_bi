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
          <el-form-item label="Agent 规划">
            <el-radio-group v-model="form.agent_planner_mode">
              <el-radio value="llm_only">全部走 LLM</el-radio>
              <el-radio value="heuristic_then_llm">启发式优先，LLM 兜底</el-radio>
            </el-radio-group>
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
            <el-button :loading="testing" @click="testConfig">
              测试连接
            </el-button>
          </el-form-item>
        </el-form>
        </el-card>
      </el-col>
      <el-col :xs=”24” :md=”8”>
        <el-card>
        <template #header>
          <span class=”card-header-title”>说明</span>
        </template>
        <el-space direction=”vertical” alignment=”start” class=”info-card”>
          <div>仅管理员可修改配置</div>
          <div>API Key 留空表示保持原值</div>
          <div>Agent 默认建议使用”全部走 LLM”</div>
        </el-space>
        </el-card>
      </el-col>
    </el-row>

    <!-- Notification Channels -->
    <el-row :gutter=”16” style=”margin-top: 20px”>
      <el-col :xs=”24” :md=”16”>
        <el-card>
          <template #header>
            <div class=”card-header”>
              <span class=”card-header-title”>通知渠道配置</span>
              <el-button size=”small” @click=”loadNotification”>刷新</el-button>
            </div>
          </template>

          <!-- WeChat Work -->
          <div class=”channel-section”>
            <div class=”channel-header”>
              <el-switch v-model=”notify.wechat_enabled” />
              <span class=”channel-title”>企业微信机器人</span>
            </div>
            <el-form label-width=”110px” class=”page-stack” v-if=”notify.wechat_enabled”>
              <el-form-item label=”Webhook URL”>
                <el-input v-model=”notify.wechat_webhook_url” placeholder=”https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...” />
              </el-form-item>
              <el-form-item>
                <el-button size=”small” :loading=”testingWechat” @click=”testChannel('wechat')”>发送测试消息</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-divider />

          <!-- DingTalk -->
          <div class=”channel-section”>
            <div class=”channel-header”>
              <el-switch v-model=”notify.dingtalk_enabled” />
              <span class=”channel-title”>钉钉机器人</span>
            </div>
            <el-form label-width=”110px” class=”page-stack” v-if=”notify.dingtalk_enabled”>
              <el-form-item label=”Webhook URL”>
                <el-input v-model=”notify.dingtalk_webhook_url” placeholder=”https://oapi.dingtalk.com/robot/send?access_token=...” />
              </el-form-item>
              <el-form-item label=”加签密钥”>
                <el-input
                  v-model=”notify.dingtalk_secret”
                  type=”password”
                  show-password
                  :placeholder=”notify.dingtalk_secret_set ? '已设置，留空保持不变' : '选填，开启加签验证时填写'”
                />
              </el-form-item>
              <el-form-item>
                <el-button size=”small” :loading=”testingDingtalk” @click=”testChannel('dingtalk')”>发送测试消息</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-divider />

          <!-- Email -->
          <div class=”channel-section”>
            <div class=”channel-header”>
              <el-switch v-model=”notify.email_enabled” />
              <span class=”channel-title”>邮件通知（SMTP）</span>
            </div>
            <el-form label-width=”110px” class=”page-stack” v-if=”notify.email_enabled”>
              <el-form-item label=”SMTP 服务器”>
                <el-input v-model=”notify.smtp_host” placeholder=”smtp.exmail.qq.com” style=”width:220px” />
                <span style=”margin: 0 8px; color:#666”>端口</span>
                <el-input-number v-model=”notify.smtp_port” :min=”1” :max=”65535” style=”width:110px” />
                <el-checkbox v-model=”notify.smtp_use_ssl” style=”margin-left:12px”>SSL</el-checkbox>
              </el-form-item>
              <el-form-item label=”用户名”>
                <el-input v-model=”notify.smtp_username” placeholder=”sender@company.com” />
              </el-form-item>
              <el-form-item label=”密码”>
                <el-input
                  v-model=”notify.smtp_password”
                  type=”password”
                  show-password
                  :placeholder=”notify.smtp_password_set ? '已设置，留空保持不变' : '授权码或密码'”
                />
              </el-form-item>
              <el-form-item label=”发件人名称”>
                <el-input v-model=”notify.smtp_from” placeholder=”Smart BI <sender@company.com>” />
              </el-form-item>
              <el-form-item label=”测试收件人”>
                <el-input v-model=”notify.test_email_to” placeholder=”admin@company.com” style=”width:240px” />
                <el-button size=”small” :loading=”testingEmail” style=”margin-left:8px” @click=”testChannel('email')”>发送测试邮件</el-button>
              </el-form-item>
            </el-form>
          </div>

          <div style=”margin-top: 16px; text-align: right”>
            <el-button type=”primary” :loading=”savingNotify” @click=”saveNotification”>保存通知配置</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs=”24” :md=”8”>
        <el-card>
          <template #header>
            <span class=”card-header-title”>配置说明</span>
          </template>
          <el-space direction=”vertical” alignment=”start” class=”info-card”>
            <div><b>企业微信</b>：在群聊中添加机器人，复制 Webhook URL 填入即可</div>
            <div><b>钉钉</b>：创建自定义机器人，可选开启”加签”安全验证</div>
            <div><b>邮件</b>：支持 SSL/TLS 两种方式，企业邮箱建议用 465 端口 + SSL</div>
            <div style=”color:#999; font-size:12px”>预警和定时报告将使用以上渠道发送通知</div>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang=”ts”>
import { computed, onMounted, reactive, ref } from “vue”
import axios from “axios”
import { ElMessage } from “element-plus”
import { useAuthStore } from “@/store/auth”
import { useRouter } from “vue-router”

const saving = ref(false)
const testing = ref(false)
const apiKeySet = ref(false)
const authStore = useAuthStore()
const router = useRouter()

// ---- Notification channel state ----
const savingNotify = ref(false)
const testingWechat = ref(false)
const testingDingtalk = ref(false)
const testingEmail = ref(false)

const notify = reactive({
  wechat_enabled: false,
  wechat_webhook_url: “”,
  dingtalk_enabled: false,
  dingtalk_webhook_url: “”,
  dingtalk_secret: “”,
  dingtalk_secret_set: false,
  email_enabled: false,
  smtp_host: “”,
  smtp_port: 465,
  smtp_username: “”,
  smtp_password: “”,
  smtp_password_set: false,
  smtp_from: “”,
  smtp_use_ssl: true,
  test_email_to: “”,
})

const form = reactive({
  provider: "custom",
  base_url: "",
  model: "",
  temperature: 0.3,
  agent_planner_mode: "llm_only",
  api_key: ""
})

const presets: Record<string, { base_url: string; model: string }> = {
  openai: { base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  moonshot: { base_url: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  deepseek: { base_url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  gemini: {
    base_url: "https://generativelanguage.googleapis.com/v1beta",
    model: "gemini-2.5-flash-lite"
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
  form.agent_planner_mode = response.data.agent_planner_mode || "llm_only"
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

const testConfig = async () => {
  testing.value = true
  try {
    const response = await axios.post("/api/settings/llm/test", {
      provider: form.provider,
      base_url: form.base_url,
      model: form.model,
      temperature: form.temperature,
      api_key: form.api_key,
    })
    ElMessage.success(response.data.message || "连接成功")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "连接测试失败")
  } finally {
    testing.value = false
  }
}

const loadNotification = async () => {
  try {
    const { data } = await axios.get("/api/settings/notification")
    Object.assign(notify, {
      wechat_enabled: data.wechat_enabled,
      wechat_webhook_url: data.wechat_webhook_url || "",
      dingtalk_enabled: data.dingtalk_enabled,
      dingtalk_webhook_url: data.dingtalk_webhook_url || "",
      dingtalk_secret: "",
      dingtalk_secret_set: data.dingtalk_secret_set,
      email_enabled: data.email_enabled,
      smtp_host: data.smtp_host || "",
      smtp_port: data.smtp_port || 465,
      smtp_username: data.smtp_username || "",
      smtp_password: "",
      smtp_password_set: data.smtp_password_set,
      smtp_from: data.smtp_from || "",
      smtp_use_ssl: data.smtp_use_ssl,
    })
  } catch {
    // ignore
  }
}

const saveNotification = async () => {
  savingNotify.value = true
  try {
    const payload: any = {
      wechat_enabled: notify.wechat_enabled,
      wechat_webhook_url: notify.wechat_webhook_url || null,
      dingtalk_enabled: notify.dingtalk_enabled,
      dingtalk_webhook_url: notify.dingtalk_webhook_url || null,
      email_enabled: notify.email_enabled,
      smtp_host: notify.smtp_host || null,
      smtp_port: notify.smtp_port,
      smtp_username: notify.smtp_username || null,
      smtp_from: notify.smtp_from || null,
      smtp_use_ssl: notify.smtp_use_ssl,
    }
    if (notify.dingtalk_secret) payload.dingtalk_secret = notify.dingtalk_secret
    if (notify.smtp_password) payload.smtp_password = notify.smtp_password
    await axios.put("/api/settings/notification", payload)
    ElMessage.success("通知配置已保存")
    await loadNotification()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally {
    savingNotify.value = false
  }
}

const testChannel = async (channel: "wechat" | "dingtalk" | "email") => {
  const loadingRef = channel === "wechat" ? testingWechat : channel === "dingtalk" ? testingDingtalk : testingEmail
  loadingRef.value = true
  try {
    await axios.post("/api/settings/notification/test", {
      channel,
      email_to: channel === "email" ? notify.test_email_to : undefined,
    })
    ElMessage.success("测试消息发送成功")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "发送失败")
  } finally {
    loadingRef.value = false
  }
}

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    await authStore.fetchProfile()
  }
  loadConfig()
  loadNotification()
})
</script>

<style scoped>
.channel-section {
  margin-bottom: 8px;
}
.channel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.channel-title {
  font-weight: 600;
  font-size: 14px;
}
</style>
