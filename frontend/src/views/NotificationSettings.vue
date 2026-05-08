<template>
  <div class="page notification-settings">
    <el-row :gutter="16">
      <el-col :xs="24" :md="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-header-title">通知配置</span>
              <el-button size="small" @click="loadNotification">刷新</el-button>
            </div>
          </template>

          <div class="channel-section">
            <div class="channel-header">
              <el-switch v-model="notify.wechat_enabled" />
              <span class="channel-title">企业微信机器人</span>
            </div>
            <el-form v-if="notify.wechat_enabled" label-width="110px" class="page-stack">
              <el-form-item label="Webhook URL">
                <el-input v-model="notify.wechat_webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
              </el-form-item>
              <el-form-item>
                <el-button size="small" :loading="testingWechat" @click="testChannel('wechat')">发送测试消息</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-divider />

          <div class="channel-section">
            <div class="channel-header">
              <el-switch v-model="notify.dingtalk_enabled" />
              <span class="channel-title">钉钉机器人</span>
            </div>
            <el-form v-if="notify.dingtalk_enabled" label-width="110px" class="page-stack">
              <el-form-item label="Webhook URL">
                <el-input v-model="notify.dingtalk_webhook_url" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
              </el-form-item>
              <el-form-item label="加签密钥">
                <el-input
                  v-model="notify.dingtalk_secret"
                  type="password"
                  show-password
                  :placeholder="notify.dingtalk_secret_set ? '已设置，留空保持不变' : '选填，开启加签验证时填写'"
                />
              </el-form-item>
              <el-form-item>
                <el-button size="small" :loading="testingDingtalk" @click="testChannel('dingtalk')">发送测试消息</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-divider />

          <div class="channel-section">
            <div class="channel-header">
              <el-switch v-model="notify.email_enabled" />
              <span class="channel-title">邮件通知（SMTP）</span>
            </div>
            <el-form v-if="notify.email_enabled" label-width="110px" class="page-stack">
              <el-form-item label="SMTP 服务器">
                <div class="smtp-row">
                  <el-input v-model="notify.smtp_host" placeholder="smtp.exmail.qq.com" class="smtp-host" />
                  <span class="smtp-port-label">端口</span>
                  <el-input-number v-model="notify.smtp_port" :min="1" :max="65535" class="smtp-port" />
                  <el-checkbox v-model="notify.smtp_use_ssl">SSL</el-checkbox>
                </div>
              </el-form-item>
              <el-form-item label="用户名">
                <el-input v-model="notify.smtp_username" placeholder="sender@company.com" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input
                  v-model="notify.smtp_password"
                  type="password"
                  show-password
                  :placeholder="notify.smtp_password_set ? '已设置，留空保持不变' : '授权码或密码'"
                />
              </el-form-item>
              <el-form-item label="发件人名称">
                <el-input v-model="notify.smtp_from" placeholder="Smart BI <sender@company.com>" />
              </el-form-item>
              <el-form-item label="测试收件人">
                <div class="email-test-row">
                  <el-input v-model="notify.test_email_to" placeholder="admin@company.com" class="email-test-input" />
                  <el-button size="small" :loading="testingEmail" @click="testChannel('email')">发送测试邮件</el-button>
                </div>
              </el-form-item>
            </el-form>
          </div>

          <div class="form-actions">
            <el-button type="primary" :loading="savingNotify" @click="saveNotification">保存通知配置</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>
            <span class="card-header-title">配置说明</span>
          </template>
          <el-space direction="vertical" alignment="start" class="info-card">
            <div><b>企业微信</b>：在群聊中添加机器人，复制 Webhook URL 填入即可</div>
            <div><b>钉钉</b>：创建自定义机器人，可选开启"加签"安全验证</div>
            <div><b>邮件</b>：支持 SSL/TLS 两种方式，企业邮箱建议用 465 端口 + SSL</div>
            <div class="hint">预警和定时报告将使用以上渠道发送通知</div>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"

const savingNotify = ref(false)
const testingWechat = ref(false)
const testingDingtalk = ref(false)
const testingEmail = ref(false)

const notify = reactive({
  wechat_enabled: false,
  wechat_webhook_url: "",
  dingtalk_enabled: false,
  dingtalk_webhook_url: "",
  dingtalk_secret: "",
  dingtalk_secret_set: false,
  email_enabled: false,
  smtp_host: "",
  smtp_port: 465,
  smtp_username: "",
  smtp_password: "",
  smtp_password_set: false,
  smtp_from: "",
  smtp_use_ssl: true,
  test_email_to: "",
})

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
    ElMessage.error("加载通知配置失败")
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

onMounted(() => {
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

.smtp-row,
.email-test-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.smtp-host {
  max-width: 220px;
}

.smtp-port {
  width: 110px;
}

.smtp-port-label,
.hint {
  color: var(--app-text-muted);
  font-size: 12px;
}

.email-test-input {
  max-width: 240px;
}

.form-actions {
  margin-top: 16px;
  text-align: right;
}

@media (max-width: 768px) {
  .smtp-row,
  .email-test-row {
    align-items: stretch;
    flex-direction: column;
  }

  .smtp-host,
  .smtp-port,
  .email-test-input {
    max-width: none;
    width: 100%;
  }
}
</style>
