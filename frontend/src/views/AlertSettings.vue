<template>
  <div class="governance-page alert-settings">
    <section class="governance-hero">
      <div class="governance-hero-copy">
        <p class="governance-kicker">ALERT GOVERNANCE</p>
        <h2 class="governance-title">预警管理</h2>
        <p class="governance-desc">
          把核心指标的异常规则沉淀为可执行的监控任务，明确检测周期、通知方式和待办人，让异常被及时发现并进入处理流程。
        </p>
      </div>
      <div class="governance-actions">
        <el-button @click="fetchAlerts" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建预警</el-button>
      </div>
    </section>

    <section class="governance-summary-grid">
      <div class="governance-summary-card">
        <span>全部预警</span>
        <strong>{{ alertStats.total }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>启用中</span>
        <strong>{{ alertStats.active }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>邮件订阅</span>
        <strong>{{ alertStats.email }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>多渠道通知</span>
        <strong>{{ alertStats.multiChannel }}</strong>
      </div>
    </section>

    <el-card class="governance-workbench" shadow="never">
      <div class="governance-toolbar">
        <div class="governance-filters">
          <el-input
            v-model="keyword"
            class="governance-search"
            clearable
            :prefix-icon="Search"
            placeholder="搜索预警 / 指标"
          />
          <el-select
            v-model="filterDatasourceId"
            placeholder="全部数据源"
            clearable
            class="governance-filter"
            @change="fetchAlerts"
          >
            <el-option
              v-for="ds in datasourceStore.datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </div>
        <span class="governance-muted">共 {{ filteredAlerts.length }} 个结果</span>
      </div>

      <el-table :data="filteredAlerts" v-loading="loading" row-key="id" empty-text="暂无预警">
        <el-table-column label="预警" min-width="220">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ row.name }}</strong>
              <span>{{ row.content || '未填写通知内容' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="指标" min-width="150">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.metric_name || '未绑定指标' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测窗口" min-width="160">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ row.time_range }} {{ timeRangeUnitLabel(row.time_range_unit) }}</strong>
              <span>每 {{ row.check_period }} {{ checkPeriodUnitLabel(row.check_period_unit) }} 检测</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="通知方式" min-width="180">
          <template #default="{ row }">
            <div class="governance-tag-row">
              <el-tag v-if="row.notify_system" size="small" type="info" effect="plain">系统</el-tag>
              <el-tag v-if="row.notify_email" size="small" type="success" effect="plain">邮件</el-tag>
              <el-tag v-if="row.notify_wechat" size="small" type="warning" effect="plain">企微</el-tag>
              <el-tag v-if="row.notify_dingtalk" size="small" type="danger" effect="plain">钉钉</el-tag>
              <span v-if="!hasNotification(row)" class="governance-muted">未设置</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              @change="(val: boolean) => toggleActive(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button text type="success" @click="runAlert(row)" :loading="runningId === row.id">触发</el-button>
            <el-button text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑预警' : '新建预警'"
      width="min(820px, calc(100vw - 32px))"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>监控对象</h3>
            <p>先明确要监控哪个可信指标，以及规则属于哪个数据源。</p>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="预警名称" prop="name">
                <el-input v-model="form.name" placeholder="例：回款率异常预警" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="数据源" prop="datasource_id">
                <el-select v-model="form.datasource_id" placeholder="选择数据源" style="width: 100%">
                  <el-option
                    v-for="ds in datasourceStore.datasources"
                    :key="ds.id"
                    :label="ds.name"
                    :value="ds.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="选择指标" prop="metric_id">
            <el-select
              v-model="form.metric_id"
              placeholder="请选择指标"
              filterable
              clearable
              style="width: 100%"
              @change="onMetricChange"
            >
              <el-option
                v-for="m in metrics"
                :key="m.id"
                :label="m.name"
                :value="m.id"
              >
                <span>{{ m.name }}</span>
                <span style="float:right; color:#999; font-size:12px">{{ m.description }}</span>
              </el-option>
            </el-select>
          </el-form-item>
        </section>

        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>触发规则</h3>
            <p>用时间窗口、维度条件和指标阈值定义什么情况算异常。</p>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="时间范围" prop="time_range">
                <div class="inline-group">
                  <el-input-number v-model="form.time_range" :min="1" :max="365" />
                  <el-select v-model="form.time_range_unit">
                    <el-option label="天" value="day" />
                    <el-option label="周" value="week" />
                    <el-option label="月" value="month" />
                  </el-select>
                </div>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="检测通知周期">
                <div class="inline-group">
                  <span>每</span>
                  <el-input-number v-model="form.check_period" :min="1" />
                  <el-select v-model="form.check_period_unit">
                    <el-option label="分钟" value="minute" />
                    <el-option label="小时" value="hour" />
                    <el-option label="天" value="day" />
                  </el-select>
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="维度条件">
            <div class="condition-list">
              <div v-for="(cond, idx) in dimensionConditions" :key="idx" class="condition-row">
                <el-input v-model="cond.field" placeholder="字段名" />
                <el-select v-model="cond.operator">
                  <el-option label="等于" value="eq" />
                  <el-option label="不等于" value="neq" />
                  <el-option label="包含" value="contains" />
                  <el-option label="属于" value="in" />
                </el-select>
                <el-input v-model="cond.value" placeholder="值" />
                <el-button :icon="Close" circle plain @click="removeDimCond(idx)" />
              </div>
              <el-button :icon="Plus" size="small" @click="addDimCond">添加维度条件</el-button>
            </div>
          </el-form-item>

          <el-form-item label="指标条件">
            <div class="condition-list">
              <div v-for="(cond, idx) in metricConditions" :key="idx" class="condition-row">
                <el-input v-model="cond.metric" placeholder="指标名" />
                <el-select v-model="cond.operator">
                  <el-option label="大于" value="gt" />
                  <el-option label="大于等于" value="gte" />
                  <el-option label="小于" value="lt" />
                  <el-option label="小于等于" value="lte" />
                  <el-option label="等于" value="eq" />
                </el-select>
                <el-input-number v-model="cond.value" />
                <el-button :icon="Close" circle plain @click="removeMetricCond(idx)" />
              </div>
              <el-button :icon="Plus" size="small" @click="addMetricCond">添加指标条件</el-button>
            </div>
          </el-form-item>
        </section>

        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>通知与处理人</h3>
            <p>预警不是只发消息，还要指定谁负责处理、谁需要同步。</p>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="待办人">
                <el-select v-model="assigneeIds" multiple placeholder="选择待办人" style="width: 100%" filterable>
                  <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="抄送人">
                <el-select v-model="ccIds" multiple placeholder="选择抄送人" style="width: 100%" filterable>
                  <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="订阅方式">
            <div class="notify-group">
              <el-checkbox v-model="form.notify_system"><div class="notify-item"><el-icon><Bell /></el-icon><span>系统通知</span></div></el-checkbox>
              <el-checkbox v-model="form.notify_email"><div class="notify-item"><el-icon><Message /></el-icon><span>邮件通知</span></div></el-checkbox>
              <el-checkbox v-model="form.notify_wechat"><div class="notify-item"><el-icon><ChatDotRound /></el-icon><span>企业微信</span></div></el-checkbox>
              <el-checkbox v-model="form.notify_dingtalk"><div class="notify-item"><el-icon><Phone /></el-icon><span>钉钉</span></div></el-checkbox>
            </div>
          </el-form-item>

          <el-form-item label="邮件收件人" v-if="form.notify_email">
            <el-input v-model="form.email_recipients" placeholder="多个地址用英文逗号分隔：a@x.com, b@x.com" />
          </el-form-item>

          <el-form-item label="预警内容">
            <el-input
              v-model="form.content"
              type="textarea"
              :rows="4"
              placeholder="预警触发时发送的内容模板，可使用 {{metric}}、{{value}}、{{time}} 等变量"
            />
          </el-form-item>
        </section>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, Close, Bell, Message, ChatDotRound, Phone, Search } from "@element-plus/icons-vue"
import axios from "axios"
import { useDatasourceStore } from "@/store/datasource"

const datasourceStore = useDatasourceStore()

// ---- State ----
const loading = ref(false)
const saving = ref(false)
const runningId = ref<number | null>(null)
const alerts = ref<any[]>([])
const metrics = ref<any[]>([])
const users = ref<any[]>([])
const keyword = ref("")
const filterDatasourceId = ref<number | null>(null)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const defaultForm = () => ({
  name: "",
  datasource_id: datasourceStore.currentId ?? null,
  metric_id: null as number | null,
  metric_name: "",
  time_range: 1,
  time_range_unit: "day",
  check_period: 1,
  check_period_unit: "hour",
  notify_system: true,
  notify_email: false,
  notify_wechat: false,
  notify_dingtalk: false,
  email_recipients: "",
  content: "",
  is_active: true,
})

const form = reactive(defaultForm())
const dimensionConditions = ref<Array<{ field: string; operator: string; value: string }>>([])
const metricConditions = ref<Array<{ metric: string; operator: string; value: number }>>([])
const assigneeIds = ref<number[]>([])
const ccIds = ref<number[]>([])

const rules: FormRules = {
  name: [{ required: true, message: "请输入预警名称", trigger: "blur" }],
  datasource_id: [{ required: true, message: "请选择数据源", trigger: "change" }],
}

const hasNotification = (row: any) =>
  Boolean(row.notify_system || row.notify_email || row.notify_wechat || row.notify_dingtalk)

const alertStats = computed(() => {
  const total = alerts.value.length
  const active = alerts.value.filter(item => item.is_active).length
  const email = alerts.value.filter(item => item.notify_email).length
  const multiChannel = alerts.value.filter(item => [
    item.notify_system,
    item.notify_email,
    item.notify_wechat,
    item.notify_dingtalk,
  ].filter(Boolean).length > 1).length
  return { total, active, email, multiChannel }
})

const filteredAlerts = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return alerts.value
  return alerts.value.filter(item =>
    [item.name, item.metric_name, item.content]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  )
})

// ---- Labels ----
function timeRangeUnitLabel(unit: string) {
  return { day: "天", week: "周", month: "月" }[unit] ?? unit
}
function checkPeriodUnitLabel(unit: string) {
  return { minute: "分钟", hour: "小时", day: "天" }[unit] ?? unit
}

// ---- Data fetching ----
async function fetchAlerts() {
  loading.value = true
  try {
    const params = filterDatasourceId.value ? { datasource_id: filterDatasourceId.value } : {}
    const { data } = await axios.get("/api/alerts", { params })
    alerts.value = data.items
  } finally {
    loading.value = false
  }
}

async function fetchMetrics() {
  const { data } = await axios.get("/api/metrics")
  metrics.value = data.items
}

async function fetchUsers() {
  try {
    const { data } = await axios.get("/api/users")
    users.value = data
  } catch {
    // non-admin users may not have access; ignore
  }
}

// ---- Condition helpers ----
function addDimCond() {
  dimensionConditions.value.push({ field: "", operator: "eq", value: "" })
}
function removeDimCond(idx: number) {
  dimensionConditions.value.splice(idx, 1)
}
function addMetricCond() {
  metricConditions.value.push({ metric: form.metric_name || "", operator: "gt", value: 0 })
}
function removeMetricCond(idx: number) {
  metricConditions.value.splice(idx, 1)
}

function onMetricChange(id: number) {
  const m = metrics.value.find((x) => x.id === id)
  if (m) form.metric_name = m.name
}

// ---- Dialog ----
function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  dimensionConditions.value = []
  metricConditions.value = []
  assigneeIds.value = []
  ccIds.value = []
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    datasource_id: row.datasource_id,
    metric_id: row.metric_id,
    metric_name: row.metric_name,
    time_range: row.time_range,
    time_range_unit: row.time_range_unit,
    check_period: row.check_period,
    check_period_unit: row.check_period_unit,
    notify_system: row.notify_system,
    notify_email: row.notify_email,
    notify_wechat: row.notify_wechat,
    notify_dingtalk: row.notify_dingtalk,
    email_recipients: row.email_recipients || "",
    content: row.content,
    is_active: row.is_active,
  })
  dimensionConditions.value = row.dimension_conditions
    ? JSON.parse(row.dimension_conditions)
    : []
  metricConditions.value = row.metric_conditions
    ? JSON.parse(row.metric_conditions)
    : []
  assigneeIds.value = row.assignees ? JSON.parse(row.assignees) : []
  ccIds.value = row.cc_users ? JSON.parse(row.cc_users) : []
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      ...form,
      dimension_conditions: JSON.stringify(dimensionConditions.value),
      metric_conditions: JSON.stringify(metricConditions.value),
      assignees: JSON.stringify(assigneeIds.value),
      cc_users: JSON.stringify(ccIds.value),
    }
    if (editingId.value) {
      await axios.put(`/api/alerts/${editingId.value}`, payload)
      ElMessage.success("预警已更新")
    } else {
      await axios.post("/api/alerts", payload)
      ElMessage.success("预警已创建")
    }
    dialogVisible.value = false
    fetchAlerts()
  } finally {
    saving.value = false
  }
}

async function runAlert(row: any) {
  runningId.value = row.id
  try {
    const { data } = await axios.post(`/api/alerts/${row.id}/run`)
    ElMessage.success(data.message || "已触发，请稍后查看历史记录")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "触发失败")
  } finally {
    runningId.value = null
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确认删除预警「${row.name}」？`, "删除确认", { type: "warning" })
  await axios.delete(`/api/alerts/${row.id}`)
  ElMessage.success("已删除")
  fetchAlerts()
}

async function toggleActive(row: any, val: boolean) {
  await axios.put(`/api/alerts/${row.id}`, { is_active: val })
  row.is_active = val
}

// ---- Lifecycle ----
onMounted(async () => {
  await datasourceStore.fetchDatasources()
  fetchAlerts()
  fetchMetrics()
  fetchUsers()
})
</script>

<style scoped>
.alert-settings {
  padding: 0;
}

.inline-group {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.inline-group :deep(.el-input-number),
.inline-group :deep(.el-select) {
  flex: 1;
}

.condition-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.condition-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) 120px minmax(120px, 1fr) 36px;
  gap: 8px;
  align-items: center;
}

.notify-group {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
}

.notify-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

@media (max-width: 700px) {
  .condition-row {
    grid-template-columns: 1fr;
  }

  .condition-row :deep(.el-button) {
    width: 36px;
  }
}
</style>
