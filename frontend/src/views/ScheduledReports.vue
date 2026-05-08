<template>
  <div class="governance-page scheduled-reports">
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
        <el-button :icon="Refresh" @click="fetchReports" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建定时报告</el-button>
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
            placeholder="搜索报告 / 问题"
          />
          <el-select
            v-model="filterDatasetId"
            placeholder="全部数据集"
            clearable
            class="governance-filter"
            @change="fetchReports"
          >
            <el-option
              v-for="ds in datasets"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </div>
        <div class="governance-quick-filters">
          <button
            v-for="item in reportQuickFilters"
            :key="item.value"
            type="button"
            class="governance-pill"
            :class="{ 'is-active': quickFilter === item.value }"
            @click="quickFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="governance-muted">共 {{ filteredReports.length }} 个结果</span>
      </div>

      <el-table class="governance-table" :data="filteredReports" v-loading="loading" row-key="id" empty-text="暂无定时报告">
        <template #empty>
          <div class="governance-empty">
            <strong>还没有匹配的定时报告</strong>
            <span>把固定经营问题沉淀为自动报告，让团队按日、周、月持续收到同一口径的数据结论。</span>
            <el-button type="primary" :icon="Plus" @click="openCreate">新建定时报告</el-button>
          </div>
        </template>
        <el-table-column label="报告" min-width="260">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ row.name }}</strong>
              <span>{{ row.question }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="定时规则" min-width="160">
          <template #default="{ row }">
            <div class="governance-table-name">
              <el-tag size="small" type="info" effect="plain">{{ row.cron_expression }}</el-tag>
              <span>{{ describeCron(row.cron_expression) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="通知方式" min-width="160">
          <template #default="{ row }">
            <div class="governance-tag-row">
              <el-tag v-if="row.notify_email" size="small" type="success" effect="plain">邮件</el-tag>
              <el-tag v-if="row.notify_wechat" size="small" type="warning" effect="plain">企微</el-tag>
              <el-tag v-if="row.notify_dingtalk" size="small" type="danger" effect="plain">钉钉</el-tag>
              <span v-if="!hasNotification(row)" class="governance-muted">未设置</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最近执行" min-width="150">
          <template #default="{ row }">
            <span v-if="row.last_run_at">{{ formatDate(row.last_run_at) }}</span>
            <span v-else class="governance-muted">从未执行</span>
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
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <div class="governance-action-group">
              <el-button text type="success" :icon="CaretRight" @click="runNow(row)" :loading="runningId === row.id">执行</el-button>
              <el-button text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button text @click="openLogs(row)">执行历史</el-button>
              <el-dropdown trigger="click">
                <el-button text :icon="MoreFilled">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :icon="Delete" @click="handleDelete(row)">删除报告</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑定时报告' : '新建定时报告'"
      width="min(980px, calc(100vw - 32px))"
      class="governance-modal"
      destroy-on-close 
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-tabs v-model="dialogActiveTab" class="modal-tabs">
          <el-tab-pane label="报告内容" name="content">
            <div class="modal-tab-content">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="报告名称" prop="name">
                    <el-input v-model="form.name" placeholder="例：每日销售汇报" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="数据集" prop="dataset_id">
                    <el-select v-model="form.dataset_id" placeholder="选择数据集" style="width: 100%">
                      <el-option v-for="ds in datasets" :key="ds.id" :label="ds.name" :value="ds.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="查询问题" prop="question">
                <el-input v-model="form.question" type="textarea" :rows="4" placeholder="例：统计今日各产线异常数量，按数量降序排列" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="执行计划" name="schedule">
            <div class="modal-tab-content">
              <el-form-item label="Cron 表达式" prop="cron_expression">
                <div class="cron-editor">
                  <el-input v-model="form.cron_expression" placeholder="0 9 * * 1-5" />
                  <span class="governance-muted">{{ describeCron(form.cron_expression) }}</span>
                </div>
              </el-form-item>
              <div class="cron-presets">
                <span class="governance-muted">快捷选择</span>
                <el-tag v-for="p in cronPresets" :key="p.value" class="cron-preset-tag" :class="{ 'is-active': form.cron_expression === p.value }" size="small" effect="plain" @click="form.cron_expression = p.value">{{ p.label }}</el-tag>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="通知方式" name="notify">
            <div class="modal-tab-content">
              <el-form-item label="推送渠道">
                <div class="notify-group">
                  <el-checkbox v-model="form.notify_email"><div class="notify-item"><el-icon><Message /></el-icon><span>邮件</span></div></el-checkbox>
                  <el-checkbox v-model="form.notify_wechat"><div class="notify-item"><el-icon><ChatDotRound /></el-icon><span>企业微信</span></div></el-checkbox>
                  <el-checkbox v-model="form.notify_dingtalk"><div class="notify-item"><el-icon><Phone /></el-icon><span>钉钉</span></div></el-checkbox>
                </div>
              </el-form-item>
              <el-form-item label="邮件收件人" v-if="form.notify_email">
                <el-input v-model="form.email_recipients" placeholder="多个地址用英文逗号分隔：a@x.com, b@x.com" />
              </el-form-item>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>

      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">保存后可在列表手动执行。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Execution History Drawer -->
    <el-drawer v-model="logsDrawer" title="执行历史" size="600px" destroy-on-close>
      <div v-if="logsLoading" style="text-align:center;padding:40px"><el-text type="info">加载中…</el-text></div>
      <div v-else-if="!executionLogs.length" style="text-align:center;padding:40px"><el-empty description="暂无执行记录" /></div>
      <div v-else class="exec-log-list">
        <div v-for="log in executionLogs" :key="log.id" class="exec-log-item" :class="log.status">
          <div class="exec-log-header">
            <el-tag :type="log.status === 'success' ? 'success' : 'danger'" size="small" effect="plain">{{ log.status === 'success' ? '成功' : '失败' }}</el-tag>
            <span class="exec-log-time">{{ formatDate(log.run_at) }}</span>
          </div>
          <div v-if="log.error_message" class="exec-log-error">{{ log.error_message }}</div>
          <div v-if="log.content_preview" class="exec-log-preview">{{ log.content_preview }}</div>
          <div v-if="log.notify_result" class="exec-log-notify">
            <el-text type="info" size="small">通知: {{ JSON.stringify(log.notify_result) }}</el-text>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import * as echarts from "echarts"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, CaretRight, Search, MoreFilled, Refresh, Message, ChatDotRound, Phone } from "@element-plus/icons-vue"
import axios from "axios"
const loading = ref(false)
const saving = ref(false)
const reports = ref<any[]>([])
const datasets = ref<any[]>([])
const keyword = ref("")
const quickFilter = ref("all")
const filterDatasetId = ref<number | null>(null)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const dialogActiveTab = ref("content")
const formRef = ref<FormInstance>()
const runningId = ref<number | null>(null)
const logsDrawer = ref(false)
const logsLoading = ref(false)
const executionLogs = ref<any[]>([])

const openLogs = async (row: any) => {
  logsDrawer.value = true
  logsLoading.value = true
  executionLogs.value = []
  try {
    const { data } = await axios.get(`/api/scheduled-reports/${row.id}/logs`)
    executionLogs.value = data
  } catch {
    ElMessage.error("加载执行历史失败")
  } finally {
    logsLoading.value = false
  }
}

const cronPresets = [
  { label: "工作日早9点", value: "0 9 * * 1-5" },
  { label: "每天早8点", value: "0 8 * * *" },
  { label: "每周一早9点", value: "0 9 * * 1" },
  { label: "每月1号早9点", value: "0 9 1 * *" },
  { label: "每小时", value: "0 * * * *" },
]

const defaultForm = () => ({
  name: "",
  dataset_id: null as number | null,
  question: "",
  cron_expression: "0 9 * * 1-5",
  notify_email: false,
  notify_wechat: false,
  notify_dingtalk: false,
  email_recipients: "",
  is_active: true,
})

const form = reactive(defaultForm())

const rules: FormRules = {
  name: [{ required: true, message: "请输入报告名称", trigger: "blur" }],
  dataset_id: [{ required: true, message: "请选择数据集", trigger: "change" }],
  question: [{ required: true, message: "请输入查询问题", trigger: "blur" }],
  cron_expression: [{ required: true, message: "请输入 Cron 表达式", trigger: "blur" }],
}

const hasNotification = (row: any) => Boolean(row.notify_email || row.notify_wechat || row.notify_dingtalk)

const reportStats = computed(() => {
  const total = reports.value.length
  const active = reports.value.filter(item => item.is_active).length
  const ran = reports.value.filter(item => item.last_run_at).length
  const notified = reports.value.filter(hasNotification).length
  return { total, active, ran, notified }
})

const reportQuickFilters = [
  { label: "全部", value: "all" },
  { label: "启用中", value: "active" },
  { label: "未配置通知", value: "no_notify" },
  { label: "从未执行", value: "never_run" },
  { label: "已禁用", value: "inactive" },
]

const filteredReports = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return reports.value.filter(item => {
    if (quickFilter.value === "active" && !item.is_active) return false
    if (quickFilter.value === "inactive" && item.is_active) return false
    if (quickFilter.value === "no_notify" && hasNotification(item)) return false
    if (quickFilter.value === "never_run" && item.last_run_at) return false
    if (!kw) return true
    return [item.name, item.question, item.cron_expression]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  })
})

function describeCron(expr: string): string {
  if (!expr) return ""
  const presetMap: Record<string, string> = {
    "0 9 * * 1-5": "工作日每天 09:00",
    "0 8 * * *": "每天 08:00",
    "0 9 * * 1": "每周一 09:00",
    "0 9 1 * *": "每月 1 号 09:00",
    "0 * * * *": "每小时整点",
  }
  return presetMap[expr.trim()] || "自定义"
}

function formatDate(dt: string): string {
  return new Date(dt).toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  })
}

async function fetchReports() {
  loading.value = true
  try {
    const params = filterDatasetId.value ? { dataset_id: filterDatasetId.value } : {}
    const { data } = await axios.get("/api/scheduled-reports", { params })
    reports.value = data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  dialogActiveTab.value = "content"
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  dialogActiveTab.value = "content"
  Object.assign(form, {
    name: row.name,
    dataset_id: row.dataset_id,
    question: row.question,
    cron_expression: row.cron_expression,
    notify_email: row.notify_email,
    notify_wechat: row.notify_wechat,
    notify_dingtalk: row.notify_dingtalk,
    email_recipients: row.email_recipients || "",
    is_active: row.is_active,
  })
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await axios.put(`/api/scheduled-reports/${editingId.value}`, { ...form })
      ElMessage.success("已更新")
    } else {
      await axios.post("/api/scheduled-reports", { ...form })
      ElMessage.success("已创建")
    }
    dialogVisible.value = false
    fetchReports()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确认删除报告「${row.name}」？`, "删除确认", { type: "warning" })
  await axios.delete(`/api/scheduled-reports/${row.id}`)
  ElMessage.success("已删除")
  fetchReports()
}

async function toggleActive(row: any, val: boolean) {
  await axios.put(`/api/scheduled-reports/${row.id}`, { is_active: val })
  row.is_active = val
}

async function runNow(row: any) {
  runningId.value = row.id
  try {
    const { data } = await axios.post(`/api/scheduled-reports/${row.id}/run`)
    ElMessage.success(data.message || "已触发执行")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "触发失败")
  } finally {
    runningId.value = null
  }
}

const donutRef = ref<HTMLElement | null>(null)
let donutChart: echarts.ECharts | null = null

const legendItems = computed(() => [
  { label: "全部报告",   value: reportStats.value.total,    color: "#3b82f6" },
  { label: "启用中",     value: reportStats.value.active,   color: "#16a34a" },
  { label: "已执行过",   value: reportStats.value.ran,      color: "#d97706" },
  { label: "已配置通知", value: reportStats.value.notified, color: "#8b5cf6" },
])

const updateDonut = () => {
  if (!donutRef.value) return
  if (!donutChart) donutChart = echarts.init(donutRef.value)
  const s = reportStats.value
  const data = [
    { value: s.active,   name: "启用中",     itemStyle: { color: "#16a34a" } },
    { value: s.ran - s.active < 0 ? 0 : s.ran - s.active, name: "未启用",   itemStyle: { color: "#94a3b8" } },
    { value: Math.max(0, s.total - s.ran), name: "从未执行", itemStyle: { color: "#e2e8f0" } },
  ].filter(d => d.value > 0)
  if (!data.length) data.push({ value: 1, name: "暂无数据", itemStyle: { color: "#e2e8f0" } })
  donutChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{ type: "pie", radius: ["52%", "80%"], center: ["50%", "50%"], avoidLabelOverlap: false,
      label: { show: true, position: "center",
        formatter: () => `{total|${s.total}}\n{label|报告总数}`,
        rich: { total: { fontSize: 22, fontWeight: 700, color: "#1e293b", lineHeight: 28 }, label: { fontSize: 11, color: "#94a3b8", lineHeight: 18 } } },
      emphasis: { label: { show: true } }, labelLine: { show: false }, data }],
  }, true)
}

watch(reportStats, () => nextTick(updateDonut), { deep: true })
onBeforeUnmount(() => { donutChart?.dispose(); donutChart = null })

async function fetchDatasets() {
  try {
    const { data } = await axios.get("/api/datasets", { params: { page: 1, page_size: 200 } })
    datasets.value = data.items || []
  } catch { /* ignore */ }
}

onMounted(async () => {
  fetchDatasets()
  fetchReports()
  nextTick(updateDonut)
})
</script>

<style scoped>
.scheduled-reports { padding: 0; }


.notify-group {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.notify-group :deep(.el-checkbox) {
  min-height: 44px;
  padding: 10px 12px;
  margin-right: 0;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.notify-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cron-editor {
  display: grid;
  grid-template-columns: minmax(180px, 260px) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}

.cron-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: -4px;
}
.cron-preset-tag {
  cursor: pointer;
  padding: 7px 10px;
}
.cron-preset-tag.is-active {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.1);
  color: var(--app-primary-dark);
}
.cron-preset-tag:hover {
  border-color: var(--app-primary);
  color: var(--app-primary);
}

@media (max-width: 640px) {
  .cron-editor {
    grid-template-columns: 1fr;
  }

  .notify-group {
    grid-template-columns: 1fr;
  }
}

.exec-log-list { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.exec-log-item { border: 1px solid var(--app-border); border-radius: 8px; padding: 12px 16px; }
.exec-log-item.error { border-color: var(--el-color-danger-light-5); background: var(--el-color-danger-light-9); }
.exec-log-item.success { border-color: var(--el-color-success-light-5); }
.exec-log-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.exec-log-time { font-size: 12px; color: var(--app-text-muted); }
.exec-log-error { font-size: 13px; color: var(--el-color-danger); margin-top: 6px; }
.exec-log-preview { font-size: 12px; color: var(--app-text-muted); white-space: pre-wrap; max-height: 120px; overflow: auto; margin-top: 6px; border-top: 1px solid var(--app-border); padding-top: 6px; }
.exec-log-notify { margin-top: 6px; }
</style>
