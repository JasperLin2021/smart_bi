<template>
  <div class="page wechat-work-page">
    <div class="page-toolbar">
      <div>
        <h2 class="page-heading">企业微信集成</h2>
        <p class="page-subtitle">配置企业微信登录、组织绑定、部门权限映射和应用消息投递。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="基础配置" name="config">
        <section class="settings-panel">
          <div class="section-header">
            <div>
              <h3>应用配置</h3>
              <p>企业微信自建应用的 CorpID、AgentID、Secret 和回调地址。</p>
            </div>
            <el-switch
              v-model="config.enabled"
              active-text="启用"
              inactive-text="停用"
            />
          </div>

          <el-form label-width="120px" class="settings-form">
            <el-form-item label="配置名称">
              <el-input v-model="config.name" placeholder="企业微信" />
            </el-form-item>
            <el-form-item label="CorpID" required>
              <el-input v-model="config.corp_id" placeholder="wwxxxxxxxxxxxxxxxx" />
            </el-form-item>
            <el-form-item label="AgentID" required>
              <el-input v-model="config.agent_id" placeholder="1000002" />
            </el-form-item>
            <el-form-item label="应用 Secret">
              <el-input
                v-model="config.app_secret"
                type="password"
                show-password
                :placeholder="config.app_secret_set ? '已设置，留空保持不变' : '请输入应用 Secret'"
              />
            </el-form-item>
            <el-form-item label="回调地址" required>
              <el-input v-model="config.callback_url" placeholder="https://bi.example.com/api/auth/wechat-work/callback" />
            </el-form-item>
            <el-form-item label="群机器人">
              <el-input v-model="config.robot_webhook_url" placeholder="选填，保留原有企业微信群机器人通道" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingConfig" @click="saveConfig">保存配置</el-button>
            </el-form-item>
          </el-form>
        </section>
      </el-tab-pane>

      <el-tab-pane label="组织绑定" name="bindings">
        <section class="settings-panel">
          <div class="section-header">
            <div>
              <h3>CorpID 绑定本地企业</h3>
              <p>用户企微登录后，根据 CorpID 定位 Smart BI 内部企业。</p>
            </div>
          </div>

          <el-form label-width="120px" class="inline-form">
            <el-form-item label="企微 CorpID" required>
              <el-input v-model="bindingForm.external_corp_id" placeholder="wwxxxxxxxxxxxxxxxx" />
            </el-form-item>
            <el-form-item label="本地企业" required>
              <el-select v-model="bindingForm.org_id" filterable placeholder="选择企业">
                <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Plus" :loading="savingBinding" @click="saveOrgBinding">新增绑定</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="orgBindings" stripe class="data-table">
            <el-table-column prop="external_corp_id" label="企微 CorpID" min-width="180" />
            <el-table-column prop="org_name" label="本地企业" min-width="160" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" text :icon="Delete" @click="deleteOrgBinding(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="部门权限" name="mappings">
        <section class="settings-panel">
          <div class="section-header">
            <div>
              <h3>部门映射权限</h3>
              <p>命中多个部门时按优先级从小到大匹配，不允许通过外部部门授予超级管理员。</p>
            </div>
          </div>

          <el-form label-width="120px" class="mapping-form">
            <div class="form-grid">
              <el-form-item label="企微 CorpID" required>
                <el-input v-model="mappingForm.external_corp_id" placeholder="wwxxxxxxxxxxxxxxxx" />
              </el-form-item>
              <el-form-item label="部门 ID" required>
                <el-input v-model="mappingForm.external_department_id" placeholder="1" />
              </el-form-item>
              <el-form-item label="本地企业" required>
                <el-select v-model="mappingForm.org_id" filterable placeholder="选择企业">
                  <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="角色">
                <el-select v-model="mappingForm.role">
                  <el-option label="普通用户" value="user" />
                  <el-option label="企业管理员" value="org_admin" />
                </el-select>
              </el-form-item>
              <el-form-item label="数据范围">
                <el-select v-model="mappingForm.data_scope" clearable placeholder="默认">
                  <el-option label="本人数据" value="owner" />
                  <el-option label="本企业数据" value="org" />
                  <el-option label="全部数据" value="all" />
                </el-select>
              </el-form-item>
              <el-form-item label="优先级">
                <el-input-number v-model="mappingForm.priority" :min="1" :max="9999" />
              </el-form-item>
            </div>
            <el-form-item label="菜单权限 JSON">
              <el-input
                v-model="menuPermissionsText"
                type="textarea"
                :rows="3"
                placeholder='例如 {"dashboard.view": true}'
              />
            </el-form-item>
            <el-form-item label="操作权限 JSON">
              <el-input
                v-model="actionPermissionsText"
                type="textarea"
                :rows="3"
                placeholder='例如 {"dashboard.read": true}'
              />
            </el-form-item>
            <el-form-item label="启用状态">
              <el-switch v-model="mappingForm.enabled" active-text="启用" inactive-text="停用" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Plus" :loading="savingMapping" @click="saveMapping">新增映射</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="permissionMappings" stripe class="data-table">
            <el-table-column prop="external_corp_id" label="CorpID" min-width="160" />
            <el-table-column prop="external_department_id" label="部门 ID" width="120" />
            <el-table-column prop="org_name" label="企业" min-width="140" />
            <el-table-column prop="role" label="角色" width="120">
              <template #default="{ row }">
                <el-tag :type="row.role === 'org_admin' ? 'warning' : 'info'" size="small">
                  {{ roleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="data_scope" label="数据范围" width="120">
              <template #default="{ row }">{{ dataScopeLabel(row.data_scope) }}</template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="100" />
            <el-table-column prop="enabled" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? "启用" : "停用" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" text :icon="Delete" @click="deleteMapping(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="消息测试" name="test">
        <section class="settings-panel">
          <div class="section-header">
            <div>
              <h3>发送应用消息</h3>
              <p>给已绑定企业微信身份的本地用户发送一条测试消息，并记录投递结果。</p>
            </div>
          </div>

          <el-form label-width="120px" class="settings-form">
            <el-form-item label="接收用户" required>
              <el-select v-model="testForm.recipient_user_id" filterable placeholder="选择本地用户">
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="userLabel(user)"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="标题" required>
              <el-input v-model="testForm.title" placeholder="Smart BI 企业微信测试" />
            </el-form-item>
            <el-form-item label="内容" required>
              <el-input v-model="testForm.content" type="textarea" :rows="4" placeholder="这是一条企业微信应用消息测试" />
            </el-form-item>
            <el-form-item label="跳转链接">
              <el-input v-model="testForm.link_url" placeholder="选填，例如 https://bi.example.com/dashboard" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Bell" :loading="testingMessage" @click="sendTestMessage">发送测试消息</el-button>
            </el-form-item>
          </el-form>
        </section>
      </el-tab-pane>

      <el-tab-pane label="投递记录" name="deliveries">
        <section class="settings-panel">
          <div class="section-header">
            <div>
              <h3>最近 200 条消息投递</h3>
              <p>用于排查未绑定身份、接口失败、配置缺失等问题。</p>
            </div>
          </div>

          <el-table :data="deliveries" stripe class="data-table">
            <el-table-column prop="event_type" label="事件类型" min-width="180" />
            <el-table-column prop="recipient_user_id" label="本地用户" width="100" />
            <el-table-column prop="recipient_external_user_id" label="企微用户" min-width="140" />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="deliveryStatusType(row.status)" size="small">
                  {{ deliveryStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error_message" label="失败原因" min-width="220" show-overflow-tooltip />
            <el-table-column label="时间" width="180">
              <template #default="{ row }">{{ formatDate(row.sent_at || row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Bell, Delete, Plus, Refresh } from "@element-plus/icons-vue"

type OrgItem = {
  id: number
  name: string
}

type UserItem = {
  id: number
  username: string
  role: string
  org_name?: string | null
}

type OrgBinding = {
  id: number
  external_corp_id: string
  org_id: number
  org_name?: string | null
}

type PermissionMapping = {
  id: number
  external_corp_id: string
  external_department_id: string
  org_id: number
  org_name?: string | null
  role: string
  data_scope?: string | null
  priority: number
  enabled: boolean
}

type MessageDelivery = {
  id: number
  event_type: string
  recipient_user_id?: number | null
  recipient_external_user_id?: string | null
  title: string
  status: string
  error_message?: string | null
  created_at?: string | null
  sent_at?: string | null
}

const activeTab = ref("config")
const loading = ref(false)
const savingConfig = ref(false)
const savingBinding = ref(false)
const savingMapping = ref(false)
const testingMessage = ref(false)

const organizations = ref<OrgItem[]>([])
const users = ref<UserItem[]>([])
const orgBindings = ref<OrgBinding[]>([])
const permissionMappings = ref<PermissionMapping[]>([])
const deliveries = ref<MessageDelivery[]>([])
const menuPermissionsText = ref("")
const actionPermissionsText = ref("")

const config = reactive({
  enabled: false,
  name: "企业微信",
  corp_id: "",
  agent_id: "",
  app_secret: "",
  app_secret_set: false,
  callback_url: "",
  robot_webhook_url: "",
})

const bindingForm = reactive({
  external_corp_id: "",
  org_id: null as number | null,
})

const mappingForm = reactive({
  external_corp_id: "",
  external_department_id: "",
  org_id: null as number | null,
  role: "user",
  data_scope: "owner",
  priority: 100,
  enabled: true,
})

const testForm = reactive({
  recipient_user_id: null as number | null,
  title: "Smart BI 企业微信测试",
  content: "这是一条企业微信应用消息测试",
  link_url: "",
})

const apiError = (error: any, fallback: string) =>
  error.response?.data?.detail || fallback

const loadConfig = async () => {
  const { data } = await axios.get("/api/integrations/wechat-work/config")
  Object.assign(config, {
    enabled: data.enabled,
    name: data.name || "企业微信",
    corp_id: data.corp_id || "",
    agent_id: data.agent_id || "",
    app_secret: "",
    app_secret_set: data.app_secret_set,
    callback_url: data.callback_url || "",
    robot_webhook_url: data.robot_webhook_url || "",
  })
}

const saveConfig = async () => {
  savingConfig.value = true
  try {
    const payload: any = {
      enabled: config.enabled,
      name: config.name || "企业微信",
      corp_id: config.corp_id || null,
      agent_id: config.agent_id || null,
      callback_url: config.callback_url || null,
      robot_webhook_url: config.robot_webhook_url || null,
    }
    if (config.app_secret) payload.app_secret = config.app_secret
    await axios.put("/api/integrations/wechat-work/config", payload)
    ElMessage.success("企业微信配置已保存")
    await loadConfig()
  } catch (error: any) {
    ElMessage.error(apiError(error, "保存企业微信配置失败"))
  } finally {
    savingConfig.value = false
  }
}

const loadOrganizations = async () => {
  const { data } = await axios.get("/api/organizations")
  organizations.value = data
}

const loadUsers = async () => {
  const { data } = await axios.get("/api/users")
  users.value = data
}

const loadOrgBindings = async () => {
  const { data } = await axios.get("/api/integrations/wechat-work/org-bindings")
  orgBindings.value = data
}

const loadMappings = async () => {
  const { data } = await axios.get("/api/integrations/wechat-work/permission-mappings")
  permissionMappings.value = data
}

const loadDeliveries = async () => {
  const { data } = await axios.get("/api/integrations/wechat-work/message-deliveries")
  deliveries.value = data
}

const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadConfig(),
      loadOrganizations(),
      loadUsers(),
      loadOrgBindings(),
      loadMappings(),
      loadDeliveries(),
    ])
  } catch (error: any) {
    ElMessage.error(apiError(error, "加载企业微信集成配置失败"))
  } finally {
    loading.value = false
  }
}

const saveOrgBinding = async () => {
  if (!bindingForm.external_corp_id || !bindingForm.org_id) {
    ElMessage.warning("请填写 CorpID 并选择本地企业")
    return
  }
  savingBinding.value = true
  try {
    await axios.post("/api/integrations/wechat-work/org-bindings", {
      external_corp_id: bindingForm.external_corp_id,
      org_id: bindingForm.org_id,
    })
    ElMessage.success("组织绑定已新增")
    bindingForm.external_corp_id = ""
    bindingForm.org_id = null
    await loadOrgBindings()
  } catch (error: any) {
    ElMessage.error(apiError(error, "新增组织绑定失败"))
  } finally {
    savingBinding.value = false
  }
}

const deleteOrgBinding = async (row: OrgBinding) => {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.external_corp_id} 的组织绑定？`, "删除绑定", { type: "warning" })
    await axios.delete(`/api/integrations/wechat-work/org-bindings/${row.id}`)
    ElMessage.success("组织绑定已删除")
    await loadOrgBindings()
  } catch {
    // cancelled
  }
}

const parsePermissions = (rawValue: string, fieldLabel: string) => {
  if (!rawValue.trim()) return null
  try {
    const parsed = JSON.parse(rawValue)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("invalid object")
    }
    return parsed
  } catch {
    ElMessage.error(`${fieldLabel} 必须是 JSON 对象`)
    throw new Error("invalid permissions json")
  }
}

const saveMapping = async () => {
  if (!mappingForm.external_corp_id || !mappingForm.external_department_id || !mappingForm.org_id) {
    ElMessage.warning("请填写 CorpID、部门 ID 并选择本地企业")
    return
  }
  savingMapping.value = true
  try {
    await axios.post("/api/integrations/wechat-work/permission-mappings", {
      external_corp_id: mappingForm.external_corp_id,
      external_department_id: mappingForm.external_department_id,
      org_id: mappingForm.org_id,
      role: mappingForm.role,
      data_scope: mappingForm.data_scope || null,
      menu_permissions: parsePermissions(menuPermissionsText.value, "菜单权限"),
      action_permissions: parsePermissions(actionPermissionsText.value, "操作权限"),
      priority: mappingForm.priority,
      enabled: mappingForm.enabled,
    })
    ElMessage.success("部门权限映射已新增")
    mappingForm.external_department_id = ""
    menuPermissionsText.value = ""
    actionPermissionsText.value = ""
    await loadMappings()
  } catch (error: any) {
    if (error.message !== "invalid permissions json") {
      ElMessage.error(apiError(error, "新增部门权限映射失败"))
    }
  } finally {
    savingMapping.value = false
  }
}

const deleteMapping = async (row: PermissionMapping) => {
  try {
    await ElMessageBox.confirm(`确定删除部门 ${row.external_department_id} 的权限映射？`, "删除映射", { type: "warning" })
    await axios.delete(`/api/integrations/wechat-work/permission-mappings/${row.id}`)
    ElMessage.success("部门权限映射已删除")
    await loadMappings()
  } catch {
    // cancelled
  }
}

const sendTestMessage = async () => {
  if (!testForm.recipient_user_id || !testForm.title || !testForm.content) {
    ElMessage.warning("请选择接收用户并填写标题、内容")
    return
  }
  testingMessage.value = true
  try {
    const { data } = await axios.post("/api/integrations/wechat-work/message/test", {
      recipient_user_id: testForm.recipient_user_id,
      title: testForm.title,
      content: testForm.content,
      link_url: testForm.link_url || null,
    })
    const failedCount = data.filter((item: MessageDelivery) => item.status === "failed").length
    ElMessage[failedCount ? "warning" : "success"](failedCount ? "测试消息已记录，但投递失败，请查看记录" : "测试消息发送成功")
    await loadDeliveries()
    activeTab.value = "deliveries"
  } catch (error: any) {
    ElMessage.error(apiError(error, "发送测试消息失败"))
  } finally {
    testingMessage.value = false
  }
}

const userLabel = (user: UserItem) =>
  user.org_name ? `${user.username} / ${user.org_name}` : user.username

const roleLabel = (role: string) => {
  const labels: Record<string, string> = {
    user: "普通用户",
    org_admin: "企业管理员",
  }
  return labels[role] || role
}

const dataScopeLabel = (scope?: string | null) => {
  const labels: Record<string, string> = {
    owner: "本人",
    org: "本企业",
    all: "全部",
  }
  return scope ? labels[scope] || scope : "默认"
}

const deliveryStatusType = (status: string) => {
  const types: Record<string, string> = {
    success: "success",
    failed: "danger",
    pending: "warning",
  }
  return types[status] || "info"
}

const deliveryStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    success: "成功",
    failed: "失败",
    pending: "待发送",
  }
  return labels[status] || status
}

const formatDate = (value?: string | null) => {
  if (!value) return "-"
  return new Date(value).toLocaleString()
}

onMounted(loadAll)
</script>

<style scoped>
.wechat-work-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-heading,
.section-header h3 {
  margin: 0;
  color: var(--app-text);
  font-weight: 650;
}

.page-heading {
  font-size: 22px;
}

.section-header h3 {
  font-size: 16px;
}

.page-subtitle,
.section-header p {
  margin: 6px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.settings-tabs {
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 8px 20px 20px;
}

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 8px;
}

.settings-form {
  max-width: 820px;
}

.inline-form,
.mapping-form {
  width: 100%;
}

.inline-form :deep(.el-form-item__content),
.settings-form :deep(.el-form-item__content),
.mapping-form :deep(.el-form-item__content) {
  max-width: 620px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(260px, 1fr));
  column-gap: 20px;
}

.form-grid :deep(.el-form-item__content) {
  max-width: none;
}

.data-table {
  width: 100%;
}

@media (max-width: 900px) {
  .page-toolbar,
  .section-header {
    align-items: stretch;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .settings-tabs {
    padding: 8px 12px 16px;
  }
}
</style>
