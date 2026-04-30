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
        <el-button :icon="Refresh" @click="fetchAlerts" :loading="loading">刷新</el-button>
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
        <div class="governance-quick-filters">
          <button
            v-for="item in alertQuickFilters"
            :key="item.value"
            type="button"
            class="governance-pill"
            :class="{ 'is-active': quickFilter === item.value }"
            @click="quickFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="governance-muted">共 {{ filteredAlerts.length }} 个结果</span>
      </div>

      <el-table class="governance-table" :data="filteredAlerts" v-loading="loading" row-key="id" empty-text="暂无预警">
        <template #empty>
          <div class="governance-empty">
            <strong>还没有匹配的预警规则</strong>
            <span>为核心指标设置阈值、检测周期和通知方式，异常触发后可以进入行动闭环。</span>
            <el-button type="primary" :icon="Plus" @click="openCreate">新建预警</el-button>
          </div>
        </template>
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
            <div class="governance-action-group">
              <el-button text type="success" @click="runAlert(row)" :loading="runningId === row.id">触发</el-button>
              <el-button text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-dropdown trigger="click">
                <el-button text :icon="MoreFilled">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :icon="Delete" @click="handleDelete(row)">删除预警</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑预警' : '新建预警'"
      width="min(1080px, calc(100vw - 32px))"
      class="governance-modal"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <div class="governance-modal-shell">
          <aside class="governance-modal-rail">
            <div>
              <p class="governance-modal-title">预警配置流程</p>
              <p class="governance-modal-copy">设置异常规则、通知和负责人。</p>
            </div>
            <div class="governance-modal-steps">
              <div
                v-for="(step, index) in alertFormSteps"
                :key="step.label"
                class="governance-modal-step"
                :class="{ 'is-done': step.done }"
              >
                <span class="governance-modal-step-index">{{ index + 1 }}</span>
                <div>
                  <strong>{{ step.label }}</strong>
                  <span>{{ step.desc }}</span>
                </div>
              </div>
            </div>
            <dl class="governance-modal-facts">
              <div>
                <dt>维度条件</dt>
                <dd>{{ dimensionConditions.length }} 个</dd>
              </div>
              <div>
                <dt>指标条件</dt>
                <dd>{{ metricConditions.length }} 个</dd>
              </div>
              <div>
                <dt>通知渠道</dt>
                <dd>{{ [form.notify_system, form.notify_email, form.notify_wechat, form.notify_dingtalk].filter(Boolean).length }} 个</dd>
              </div>
            </dl>
            <div class="governance-modal-tip">至少添加一个指标条件。</div>
          </aside>

          <div class="governance-modal-main">
        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>监控对象</h3>
            <p>选择指标和数据源。</p>
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
            <p>配置窗口和阈值。</p>
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
              <div v-if="dimensionConditions.length === 0" class="condition-empty">
                默认不限制维度。需要只监控某个区域、渠道或产线时再添加条件。
              </div>
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
              <div v-if="metricConditions.length === 0" class="condition-empty">
                至少添加一个指标阈值，预警才知道什么情况算异常。
              </div>
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
            <p>指定渠道和负责人。</p>
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
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">保存后按周期检测并通知。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, Close, Bell, Message, ChatDotRound, Phone, Search, MoreFilled, Refresh } from "@element-plus/icons-vue"
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
const quickFilter = ref("all")
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

const alertFormSteps = computed(() => [
  {
    label: "监控对象",
    desc: "数据源和指标",
    done: Boolean(form.name.trim() && form.datasource_id && form.metric_id),
  },
  {
    label: "触发规则",
    desc: "窗口、条件和阈值",
    done: metricConditions.value.length > 0,
  },
  {
    label: "通知闭环",
    desc: "渠道和处理人",
    done: Boolean(
      [form.notify_system, form.notify_email, form.notify_wechat, form.notify_dingtalk].some(Boolean) &&
      (assigneeIds.value.length > 0 || form.content.trim())
    ),
  },
])

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

const alertQuickFilters = [
  { label: "全部", value: "all" },
  { label: "启用中", value: "active" },
  { label: "未配置通知", value: "no_notify" },
  { label: "多渠道", value: "multi_channel" },
  { label: "已禁用", value: "inactive" },
]

const filteredAlerts = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return alerts.value.filter(item => {
    if (quickFilter.value === "active" && !item.is_active) return false
    if (quickFilter.value === "inactive" && item.is_active) return false
    if (quickFilter.value === "no_notify" && hasNotification(item)) return false
    if (quickFilter.value === "multi_channel" && [
      item.notify_system,
      item.notify_email,
      item.notify_wechat,
      item.notify_dingtalk,
    ].filter(Boolean).length <= 1) return false
    if (!kw) return true
    return [item.name, item.metric_name, item.content]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  })
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
  gap: 10px;
  width: 100%;
}

.condition-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) 120px minmax(120px, 1fr) 36px;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.condition-empty {
  padding: 12px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text-muted);
  line-height: 1.6;
}

.notify-group {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.notify-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.notify-group :deep(.el-checkbox) {
  min-height: 44px;
  padding: 10px 12px;
  margin-right: 0;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

@media (max-width: 700px) {
  .condition-row {
    grid-template-columns: 1fr;
  }

  .condition-row :deep(.el-button) {
    width: 36px;
  }

  .notify-group {
    grid-template-columns: 1fr;
  }
}
</style>
