<template>
  <div class="alert-settings">
    <!-- Header toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="filterDatasourceId"
          placeholder="全部数据源"
          clearable
          style="width: 200px"
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
      <el-button type="primary" :icon="Plus" @click="openCreate">新建预警</el-button>
    </div>

    <!-- Alert list -->
    <el-table :data="alerts" v-loading="loading" stripe border style="margin-top: 16px">
      <el-table-column prop="name" label="预警名称" min-width="180" />
      <el-table-column label="指标" prop="metric_name" min-width="120" />
      <el-table-column label="时间范围" min-width="120">
        <template #default="{ row }">
          {{ row.time_range }} {{ timeRangeUnitLabel(row.time_range_unit) }}
        </template>
      </el-table-column>
      <el-table-column label="检测周期" min-width="120">
        <template #default="{ row }">
          每 {{ row.check_period }} {{ checkPeriodUnitLabel(row.check_period_unit) }}
        </template>
      </el-table-column>
      <el-table-column label="订阅方式" min-width="180">
        <template #default="{ row }">
          <el-tag v-if="row.notify_system" size="small" type="info" style="margin-right:4px">系统</el-tag>
          <el-tag v-if="row.notify_email" size="small" type="success" style="margin-right:4px">邮件</el-tag>
          <el-tag v-if="row.notify_wechat" size="small" type="warning" style="margin-right:4px">企微</el-tag>
          <el-tag v-if="row.notify_dingtalk" size="small" type="danger">钉钉</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            @change="(val: boolean) => toggleActive(row, val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="success" @click="runAlert(row)" :loading="runningId === row.id">触发</el-button>
          <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑预警' : '新建预警'"
      width="720px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="110px"
        label-position="left"
      >
        <!-- 选择指标 -->
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

        <!-- 预警名称 -->
        <el-form-item label="预警名称" prop="name">
          <el-input v-model="form.name" placeholder="例：关于TOTALTIMES的预警" />
        </el-form-item>

        <!-- 数据源 -->
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

        <!-- 时间范围 -->
        <el-form-item label="时间范围" prop="time_range">
          <div class="inline-group">
            <el-input-number v-model="form.time_range" :min="1" :max="365" style="width:120px" />
            <el-select v-model="form.time_range_unit" style="width:110px; margin-left:8px">
              <el-option label="天" value="day" />
              <el-option label="周" value="week" />
              <el-option label="月" value="month" />
            </el-select>
          </div>
        </el-form-item>

        <!-- 维度条件 -->
        <el-form-item label="维度条件">
          <div class="condition-list">
            <div
              v-for="(cond, idx) in dimensionConditions"
              :key="idx"
              class="condition-row"
            >
              <el-input
                v-model="cond.field"
                placeholder="字段名"
                style="width:150px"
              />
              <el-select v-model="cond.operator" style="width:110px; margin: 0 8px">
                <el-option label="等于" value="eq" />
                <el-option label="不等于" value="neq" />
                <el-option label="包含" value="contains" />
                <el-option label="属于" value="in" />
              </el-select>
              <el-input v-model="cond.value" placeholder="值" style="flex:1" />
              <el-button :icon="Close" circle plain @click="removeDimCond(idx)" style="margin-left:8px" />
            </div>
            <el-button :icon="Plus" size="small" @click="addDimCond">添加维度条件</el-button>
          </div>
        </el-form-item>

        <!-- 指标条件 -->
        <el-form-item label="指标条件">
          <div class="condition-list">
            <div
              v-for="(cond, idx) in metricConditions"
              :key="idx"
              class="condition-row"
            >
              <el-input v-model="cond.metric" placeholder="指标名" style="width:150px" />
              <el-select v-model="cond.operator" style="width:110px; margin: 0 8px">
                <el-option label="大于" value="gt" />
                <el-option label="大于等于" value="gte" />
                <el-option label="小于" value="lt" />
                <el-option label="小于等于" value="lte" />
                <el-option label="等于" value="eq" />
              </el-select>
              <el-input-number v-model="cond.value" style="width:120px" />
              <el-button :icon="Close" circle plain @click="removeMetricCond(idx)" style="margin-left:8px" />
            </div>
            <el-button :icon="Plus" size="small" @click="addMetricCond">添加指标条件</el-button>
          </div>
        </el-form-item>

        <!-- 检测通知周期 -->
        <el-form-item label="检测通知周期">
          <span style="margin-right:8px">每</span>
          <el-input-number v-model="form.check_period" :min="1" style="width:110px" />
          <el-select v-model="form.check_period_unit" style="width:100px; margin-left:8px">
            <el-option label="分钟" value="minute" />
            <el-option label="小时" value="hour" />
            <el-option label="天" value="day" />
          </el-select>
          <span style="margin-left:8px; color:#999">检测一次</span>
        </el-form-item>

        <!-- 待办人 -->
        <el-form-item label="待办人">
          <el-select
            v-model="assigneeIds"
            multiple
            placeholder="选择待办人"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="u in users"
              :key="u.id"
              :label="u.username"
              :value="u.id"
            />
          </el-select>
        </el-form-item>

        <!-- 抄送人 -->
        <el-form-item label="抄送人">
          <el-select
            v-model="ccIds"
            multiple
            placeholder="选择抄送人"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="u in users"
              :key="u.id"
              :label="u.username"
              :value="u.id"
            />
          </el-select>
        </el-form-item>

        <!-- 订阅方式 -->
        <el-form-item label="订阅方式">
          <div class="notify-group">
            <el-checkbox v-model="form.notify_system">
              <div class="notify-item">
                <el-icon><Bell /></el-icon>
                <span>系统通知</span>
              </div>
            </el-checkbox>
            <el-checkbox v-model="form.notify_email">
              <div class="notify-item">
                <el-icon><Message /></el-icon>
                <span>邮件通知</span>
              </div>
            </el-checkbox>
            <el-checkbox v-model="form.notify_wechat">
              <div class="notify-item">
                <el-icon><ChatDotRound /></el-icon>
                <span>企业微信</span>
              </div>
            </el-checkbox>
            <el-checkbox v-model="form.notify_dingtalk">
              <div class="notify-item">
                <el-icon><Phone /></el-icon>
                <span>钉钉</span>
              </div>
            </el-checkbox>
          </div>
        </el-form-item>

        <!-- 邮件收件人 -->
        <el-form-item label="邮件收件人" v-if="form.notify_email">
          <el-input
            v-model="form.email_recipients"
            placeholder="多个地址用英文逗号分隔：a@x.com, b@x.com"
          />
        </el-form-item>

        <!-- 预警内容 -->
        <el-form-item label="预警内容">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            placeholder="预警触发时发送的内容模板，可使用 {{metric}}、{{value}}、{{time}} 等变量"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, Close, Bell, Message, ChatDotRound, Phone } from "@element-plus/icons-vue"
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  gap: 12px;
  align-items: center;
}

.inline-group {
  display: flex;
  align-items: center;
}

.condition-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.condition-row {
  display: flex;
  align-items: center;
}

.notify-group {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}

.notify-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
