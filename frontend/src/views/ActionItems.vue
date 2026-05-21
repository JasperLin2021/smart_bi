<template>
  <div class="governance-page action-items-page">
    <div class="page-header">
      <div class="page-header__chart-area">
        <div ref="donutRef" class="page-donut" />
        <div class="page-legend">
          <div class="page-legend__item" v-for="item in legendItems" :key="item.label">
            <span class="page-legend__dot" :style="{ background: item.color }" />
            <span class="page-legend__label">{{ item.label }}</span>
            <strong class="page-legend__value" :style="{ color: item.color }">{{ item.value }}</strong>
          </div>
        </div>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" @click="fetchAll" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建行动项</el-button>
      </div>
    </div>

    <el-card class="governance-workbench" shadow="never">
      <div class="governance-toolbar">
        <div class="governance-filters">
          <el-input
            v-model="keyword"
            class="governance-search"
            clearable
            :prefix-icon="Search"
            placeholder="搜索行动项 / 结论"
          />
          <el-select v-model="statusFilter" clearable placeholder="状态" class="governance-filter">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="priorityFilter" clearable placeholder="优先级" class="governance-filter">
            <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="sourceFilter" clearable placeholder="来源" class="governance-filter">
            <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <span class="governance-muted">共 {{ filteredItems.length }} 个结果</span>
      </div>

      <el-table :data="filteredItems" v-loading="loading" row-key="id" empty-text="暂无行动项"
        highlight-current-row style="cursor:pointer"
        @row-click="(row: any, _c: any, e: MouseEvent) => { if (!(e.target as HTMLElement).closest('.el-button,.el-switch,.el-select,.el-dropdown')) openDetail(row) }"
      >
        <el-table-column label="行动项" min-width="280">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ row.title }}</strong>
              <span>{{ row.description || sourceSummary(row) }}</span>
              <div class="governance-tag-row">
                <el-tag size="small" :type="priorityTagType(row.priority)" effect="plain">
                  {{ priorityLabel(row.priority) }}
                </el-tag>
                <el-tag size="small" type="info" effect="plain">{{ sourceLabel(row.source_type) }}</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="关联资源" min-width="220">
          <template #default="{ row }">
            <div class="link-tags">
              <el-tag v-if="metricName(row.linked_metric_id)" size="small" effect="plain">
                指标：{{ metricName(row.linked_metric_id) }}
              </el-tag>
              <el-tag v-if="datasetName(row.linked_dataset_id)" size="small" effect="plain" type="success">
                数据集：{{ datasetName(row.linked_dataset_id) }}
              </el-tag>
              <el-tag v-if="dashboardName(row.linked_dashboard_id)" size="small" effect="plain" type="warning">
                看板：{{ dashboardName(row.linked_dashboard_id) }}
              </el-tag>
              <span v-if="!hasLinks(row)" class="governance-muted">未关联资源</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="负责人 / 截止" width="170">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ ownerLabel(row.owner_id) }}</strong>
              <span :class="dueClass(row)">{{ formatDate(row.due_date) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态与结果" min-width="220">
          <template #default="{ row }">
            <div class="governance-table-name">
              <el-select
                :model-value="row.status"
                size="small"
                class="status-select"
                @change="(value: string) => updateStatus(row, value)"
              >
                <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <span>{{ row.outcome || "尚未填写处理结果" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" :icon="Delete" @click="deleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑行动项' : '新建行动项'"
      width="min(820px, calc(100vw - 32px))"
      destroy-on-close 
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-tabs v-model="dialogActiveTab" class="modal-tabs">
          <el-tab-pane label="行动定义" name="action">
            <div class="modal-tab-content">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="标题" prop="title">
                    <el-input v-model="form.title" placeholder="例：跟进华东销售额下滑" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="来源">
                    <el-select v-model="form.source_type" style="width: 100%">
                      <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="说明">
                <el-input v-model="form.description" type="textarea" :rows="3" placeholder="补充背景、异常表现或分析结论" />
              </el-form-item>
              <el-row :gutter="16">
                <el-col :xs="24" :md="8">
                  <el-form-item label="优先级">
                    <el-select v-model="form.priority" style="width: 100%">
                      <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="状态">
                    <el-select v-model="form.status" style="width: 100%">
                      <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="截止日期">
                    <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="负责人">
                <el-tree-select
                  v-model="form.owner_id"
                  :data="assignableTree"
                  :props="{ label: 'label', children: 'children', value: 'value', disabled: 'disabled' }"
                  placeholder="按部门选择负责人"
                  filterable
                  clearable
                  check-strictly
                  style="width: 100%"
                />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="关联上下文" name="context">
            <div class="modal-tab-content">
              <el-row :gutter="16">
                <el-col :xs="24" :md="8">
                  <el-form-item label="关联指标">
                    <el-select v-model="form.linked_metric_id" clearable filterable style="width: 100%">
                      <el-option v-for="metric in metrics" :key="metric.id" :label="metric.name" :value="metric.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="关联数据集">
                    <el-select v-model="form.linked_dataset_id" clearable filterable style="width: 100%">
                      <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="关联看板">
                    <el-select v-model="form.linked_dashboard_id" clearable filterable style="width: 100%">
                      <el-option v-for="dashboard in dashboards" :key="dashboard.id" :label="dashboard.title" :value="dashboard.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="处理结果">
                <el-input v-model="form.outcome" type="textarea" :rows="3" placeholder="完成后填写处理结果、影响和后续跟踪事项" />
              </el-form-item>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveItem">保存行动项</el-button>
      </template>
    </el-dialog>

    <!-- Detail Modal -->
    <el-dialog v-model="detailVisible" width="580px" destroy-on-close class="governance-modal">
      <template #header>
        <div class="detail-modal-header" v-if="detailRow">
          <div>
            <div class="detail-modal-title">{{ detailRow.title }}</div>
            <div class="detail-modal-meta">
              <el-tag :type="priorityTagType(detailRow.priority)" effect="plain" size="small">{{ priorityLabel(detailRow.priority) }}</el-tag>
              <el-tag :type="statusTagType(detailRow.status)" size="small" effect="light" style="margin-left:6px">{{ statusLabel(detailRow.status) }}</el-tag>
            </div>
          </div>
        </div>
      </template>
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="负责人">{{ ownerLabel(detailRow.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="截止日期">
          <span :class="dueClass(detailRow)">{{ formatDate(detailRow.due_date) || '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="来源" :span="2">
          <el-tag type="info" effect="plain" size="small">{{ sourceLabel(detailRow.source_type) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="detailRow.description" label="说明" :span="2">{{ detailRow.description }}</el-descriptions-item>
        <el-descriptions-item label="关联资源" :span="2">
          <div class="link-tags">
            <el-tag v-if="metricName(detailRow.linked_metric_id)" effect="plain" size="small">指标：{{ metricName(detailRow.linked_metric_id) }}</el-tag>
            <el-tag v-if="datasetName(detailRow.linked_dataset_id)" type="success" effect="plain" size="small">数据集：{{ datasetName(detailRow.linked_dataset_id) }}</el-tag>
            <el-tag v-if="dashboardName(detailRow.linked_dashboard_id)" type="warning" effect="plain" size="small">看板：{{ dashboardName(detailRow.linked_dashboard_id) }}</el-tag>
            <span v-if="!hasLinks(detailRow)" class="muted-text">未关联资源</span>
          </div>
        </el-descriptions-item>
        <el-descriptions-item v-if="detailRow.outcome" label="处理结果" :span="2">{{ detailRow.outcome }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="openEdit(detailRow!); detailVisible = false">编辑</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import * as echarts from "echarts"
import axios from "axios"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Delete, Edit, Plus, Refresh, Search } from "@element-plus/icons-vue"
import { useAuthStore } from "@/store/auth"

interface ActionItem {
  id: number
  title: string
  description: string | null
  source_type: string
  source_id: string | null
  source_payload: Record<string, any> | null
  linked_metric_id: number | null
  linked_dataset_id: number | null
  linked_dashboard_id: number | null
  owner_id: number | null
  priority: string
  due_date: string | null
  status: string
  outcome: string | null
  created_by: number | null
}

interface MetricOption { id: number; name: string }
interface DatasetOption { id: number; name: string }
interface DashboardOption { id: number; title: string }
interface AssignableUser { id: number; username: string; role: string; role_label: string; department: string }
interface AssignableDept { department: string; users: AssignableUser[] }

const authStore = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const detailVisible = ref(false)
const detailRow = ref<ActionItem | null>(null)
const openDetail = (row: ActionItem) => { detailRow.value = row; detailVisible.value = true }
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const dialogActiveTab = ref("action")
const keyword = ref("")
const statusFilter = ref("")
const priorityFilter = ref("")
const sourceFilter = ref("")
const items = ref<ActionItem[]>([])
const metrics = ref<MetricOption[]>([])
const datasets = ref<DatasetOption[]>([])
const dashboards = ref<DashboardOption[]>([])
const assignableUsers = ref<AssignableDept[]>([])
const formRef = ref<FormInstance>()

const assignableTree = computed(() => {
  const allUsers: AssignableUser[] = []
  assignableUsers.value.forEach(dept => allUsers.push(...dept.users))

  return assignableUsers.value.map(dept => ({
    value: `dept:${dept.department}`,
    label: dept.department,
    disabled: true,
    children: dept.users.map(u => ({
      value: u.id,
      label: `${u.username}（${u.role_label}）`,
      disabled: false,
    })),
  }))
})

const statusOptions = [
  { label: "待处理", value: "open" },
  { label: "处理中", value: "in_progress" },
  { label: "已完成", value: "done" },
  { label: "已取消", value: "cancelled" },
]

const priorityOptions = [
  { label: "低", value: "low" },
  { label: "中", value: "medium" },
  { label: "高", value: "high" },
  { label: "紧急", value: "urgent" },
]

const sourceOptions = [
  { label: "手动", value: "manual" },
  { label: "问数结果", value: "query" },
  { label: "预警异常", value: "alert" },
  { label: "分析结果", value: "insight" },
  { label: "看板", value: "dashboard" },
  { label: "数据集", value: "dataset" },
  { label: "指标", value: "metric" },
]

const emptyForm = () => ({
  title: "",
  description: "",
  source_type: "manual",
  source_id: "",
  source_payload: null as Record<string, any> | null,
  linked_metric_id: null as number | null,
  linked_dataset_id: null as number | null,
  linked_dashboard_id: null as number | null,
  owner_id: authStore.profile?.id || null,
  priority: "medium",
  due_date: "",
  status: "open",
  outcome: "",
})

const form = reactive(emptyForm())

const rules: FormRules = {
  title: [{ required: true, message: "请输入行动项标题", trigger: "blur" }],
}

const resetForm = (value = emptyForm()) => {
  Object.assign(form, value)
}

const sourceLabel = (value: string) => sourceOptions.find(item => item.value === value)?.label || value
const priorityLabel = (value: string) => priorityOptions.find(item => item.value === value)?.label || value
const statusLabel = (value: string) => statusOptions.find(item => item.value === value)?.label || value

const priorityTagType = (value: string) => {
  const types: Record<string, "info" | "success" | "warning" | "danger"> = {
    low: "info",
    medium: "success",
    high: "warning",
    urgent: "danger",
  }
  return types[value] || "info"
}

const statusTagType = (value: string): "info" | "success" | "warning" | "danger" | "primary" => {
  const types: Record<string, "info" | "success" | "warning" | "danger" | "primary"> = {
    open: "info", in_progress: "primary", pending_review: "warning",
    resolved: "success", closed: "success", cancelled: "info",
  }
  return types[value] || "info"
}

const metricName = (id?: number | null) => id ? metrics.value.find(item => item.id === id)?.name : ""
const datasetName = (id?: number | null) => id ? datasets.value.find(item => item.id === id)?.name : ""
const dashboardName = (id?: number | null) => id ? dashboards.value.find(item => item.id === id)?.title : ""
const ownerLabel = (id?: number | null) => {
  if (!id) return "未指派"
  for (const dept of assignableUsers.value) {
    const u = dept.users.find(u => u.id === id)
    if (u) return `${u.username}（${u.department}）`
  }
  return id === authStore.profile?.id ? authStore.profile?.username || "我" : `用户 #${id}`
}

const hasLinks = (row: ActionItem) => Boolean(row.linked_metric_id || row.linked_dataset_id || row.linked_dashboard_id)

const sourceSummary = (row: ActionItem) => {
  const payload = row.source_payload || {}
  return payload.summary || payload.question || row.source_id || "暂无来源摘要"
}

const formatDate = (value?: string | null) => value || "未设置"

const dueClass = (row: ActionItem) => {
  if (!row.due_date || ["done", "cancelled"].includes(row.status)) return ""
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(row.due_date)
  if (due < today) return "is-overdue"
  const diffDays = (due.getTime() - today.getTime()) / 86400000
  return diffDays <= 3 ? "is-due-soon" : ""
}

const actionStats = computed(() => {
  const total = items.value.length
  const open = items.value.filter(item => ["open", "in_progress"].includes(item.status)).length
  const done = items.value.filter(item => item.status === "done").length
  const dueSoon = items.value.filter(item => dueClass(item) === "is-due-soon" || dueClass(item) === "is-overdue").length
  return { total, open, done, dueSoon }
})

const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return items.value.filter(item => {
    if (statusFilter.value && item.status !== statusFilter.value) return false
    if (priorityFilter.value && item.priority !== priorityFilter.value) return false
    if (sourceFilter.value && item.source_type !== sourceFilter.value) return false
    if (!kw) return true
    return [item.title, item.description, sourceSummary(item), item.outcome]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  })
})

const fetchItems = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/action-items")
    items.value = response.data.items || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "行动项加载失败")
  } finally {
    loading.value = false
  }
}

const fetchReferences = async () => {
  const [metricRes, datasetRes, dashboardRes, assignableRes] = await Promise.allSettled([
    axios.get("/api/metrics"),
    axios.get("/api/datasets"),
    axios.get("/api/dashboards"),
    axios.get("/api/users/assignable"),
  ])
  if (metricRes.status === "fulfilled") metrics.value = metricRes.value.data.items || []
  if (datasetRes.status === "fulfilled") datasets.value = datasetRes.value.data.items || []
  if (dashboardRes.status === "fulfilled") dashboards.value = dashboardRes.value.data.items || []
  if (assignableRes.status === "fulfilled") assignableUsers.value = assignableRes.value.data || []
}

const fetchAll = async () => {
  await Promise.all([fetchItems(), fetchReferences()])
}

const openCreate = () => {
  editingId.value = null
  dialogActiveTab.value = "action"
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row: ActionItem) => {
  editingId.value = row.id
  dialogActiveTab.value = "action"
  resetForm({
    title: row.title,
    description: row.description || "",
    source_type: row.source_type || "manual",
    source_id: row.source_id || "",
    source_payload: row.source_payload || null,
    linked_metric_id: row.linked_metric_id,
    linked_dataset_id: row.linked_dataset_id,
    linked_dashboard_id: row.linked_dashboard_id,
    owner_id: row.owner_id,
    priority: row.priority || "medium",
    due_date: row.due_date || "",
    status: row.status || "open",
    outcome: row.outcome || "",
  })
  dialogVisible.value = true
}

const payloadFromForm = () => ({
  ...form,
  source_id: form.source_id || null,
  due_date: form.due_date || null,
  description: form.description || null,
  outcome: form.outcome || null,
})

const saveItem = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await axios.put(`/api/action-items/${editingId.value}`, payloadFromForm())
    } else {
      await axios.post("/api/action-items", payloadFromForm())
    }
    ElMessage.success("行动项已保存")
    dialogVisible.value = false
    await fetchItems()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "行动项保存失败")
  } finally {
    saving.value = false
  }
}

const updateStatus = async (row: ActionItem, status: string) => {
  if (row.status === status) return
  const oldStatus = row.status
  row.status = status
  try {
    const response = await axios.put(`/api/action-items/${row.id}`, { status })
    Object.assign(row, response.data)
    ElMessage.success(`状态已更新为${statusLabel(status)}`)
  } catch (error: any) {
    row.status = oldStatus
    ElMessage.error(error.response?.data?.detail || "状态更新失败")
  }
}

const deleteItem = async (row: ActionItem) => {
  try {
    await ElMessageBox.confirm(`确定删除行动项"${row.title}"？`, "提示", { type: "warning" })
    await axios.delete(`/api/action-items/${row.id}`)
    ElMessage.success("行动项已删除")
    await fetchItems()
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error(error.response?.data?.detail || "删除失败")
    }
  }
}

const donutRef = ref<HTMLElement | null>(null)
let donutChart: echarts.ECharts | null = null

const legendItems = computed(() => [
  { label: "全部行动", value: actionStats.value.total,   color: "#3b82f6" },
  { label: "待处理",   value: actionStats.value.open,    color: "#d97706" },
  { label: "临近截止", value: actionStats.value.dueSoon, color: "#dc2626" },
  { label: "已闭环",   value: actionStats.value.done,    color: "#16a34a" },
])

const updateDonut = () => {
  if (!donutRef.value) return
  if (!donutChart) donutChart = echarts.init(donutRef.value)
  const s = actionStats.value
  const data = [
    { value: s.done,    name: "已闭环",   itemStyle: { color: "#16a34a" } },
    { value: s.open,    name: "待处理",   itemStyle: { color: "#d97706" } },
    { value: s.dueSoon, name: "临近截止", itemStyle: { color: "#dc2626" } },
    { value: Math.max(0, s.total - s.done - s.open), name: "其他", itemStyle: { color: "#94a3b8" } },
  ].filter(d => d.value > 0)
  if (!data.length) data.push({ value: 1, name: "暂无数据", itemStyle: { color: "#e2e8f0" } })
  donutChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{ type: "pie", radius: ["52%", "80%"], center: ["50%", "50%"], avoidLabelOverlap: false,
      label: { show: true, position: "center",
        formatter: () => `{total|${s.total}}\n{label|行动总数}`,
        rich: { total: { fontSize: 22, fontWeight: 700, color: "#1e293b", lineHeight: 28 }, label: { fontSize: 11, color: "#94a3b8", lineHeight: 18 } } },
      emphasis: { label: { show: true } }, labelLine: { show: false }, data }],
  }, true)
}

watch(actionStats, () => nextTick(updateDonut), { deep: true })
onBeforeUnmount(() => { donutChart?.dispose(); donutChart = null })

onMounted(() => {
  fetchAll()
  nextTick(updateDonut)
})
</script>

<style scoped>
.action-items-page :deep(.el-table .cell) {
  line-height: 1.5;
}

.detail-modal-header { display: flex; flex-direction: column; gap: 6px; }
.detail-modal-title { font-size: 15px; font-weight: 600; color: var(--app-text); }
.detail-modal-meta { display: flex; align-items: center; }
.muted-text { color: var(--app-text-muted); font-size: 13px; }

.link-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.status-select {
  width: 118px;
}

.is-overdue {
  color: var(--el-color-danger);
  font-weight: 600;
}

.is-due-soon {
  color: var(--el-color-warning);
  font-weight: 600;
}
</style>
