<template>
  <div class="governance-page scheduled-reports">
    <section class="governance-hero">
      <div class="governance-hero-copy">
        <p class="governance-kicker">REPORT AUTOMATION</p>
        <h2 class="governance-title">定时报告</h2>
        <p class="governance-desc">
          把固定经营问题变成自动执行的报告任务，按计划生成数据结论并推送给团队，减少重复问数和手工汇总。
        </p>
      </div>
      <div class="governance-actions">
        <el-button :icon="Refresh" @click="fetchReports" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建定时报告</el-button>
      </div>
    </section>

    <section class="governance-summary-grid">
      <div class="governance-summary-card">
        <span>全部报告</span>
        <strong>{{ reportStats.total }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>启用中</span>
        <strong>{{ reportStats.active }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>已执行过</span>
        <strong>{{ reportStats.ran }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>已配置通知</span>
        <strong>{{ reportStats.notified }}</strong>
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
            placeholder="搜索报告 / 问题"
          />
          <el-select
            v-model="filterDatasourceId"
            placeholder="全部数据源"
            clearable
            class="governance-filter"
            @change="fetchReports"
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
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <div class="governance-action-group">
              <el-button text type="success" :icon="CaretRight" @click="runNow(row)" :loading="runningId === row.id">执行</el-button>
              <el-button text type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
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
      width="min(760px, calc(100vw - 32px))"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>报告内容</h3>
            <p>定义报告名称、数据源和要自动执行的自然语言问题。</p>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="报告名称" prop="name">
                <el-input v-model="form.name" placeholder="例：每日销售汇报" />
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
          <el-form-item label="查询问题" prop="question">
            <el-input
              v-model="form.question"
              type="textarea"
              :rows="4"
              placeholder="例：统计今日各产线异常数量，按数量降序排列"
            />
          </el-form-item>
        </section>

        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>执行计划</h3>
            <p>选择常用计划或输入 Cron 表达式，系统会按这个规则自动执行。</p>
          </div>
          <el-form-item label="Cron 表达式" prop="cron_expression">
            <div class="cron-editor">
              <el-input v-model="form.cron_expression" placeholder="0 9 * * 1-5" />
              <span class="governance-muted">{{ describeCron(form.cron_expression) }}</span>
            </div>
          </el-form-item>
          <div class="cron-presets">
            <span class="governance-muted">快捷选择</span>
            <el-tag
              v-for="p in cronPresets"
              :key="p.value"
              class="cron-preset-tag"
              :class="{ 'is-active': form.cron_expression === p.value }"
              size="small"
              effect="plain"
              @click="form.cron_expression = p.value"
            >{{ p.label }}</el-tag>
          </div>
        </section>

        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <h3>通知方式</h3>
            <p>配置报告生成后的推送渠道。</p>
          </div>
          <el-form-item label="通知方式">
            <div class="notify-group">
              <el-checkbox v-model="form.notify_email">邮件</el-checkbox>
              <el-checkbox v-model="form.notify_wechat">企业微信</el-checkbox>
              <el-checkbox v-model="form.notify_dingtalk">钉钉</el-checkbox>
            </div>
          </el-form-item>

          <el-form-item label="邮件收件人" v-if="form.notify_email">
            <el-input v-model="form.email_recipients" placeholder="多个地址用英文逗号分隔：a@x.com, b@x.com" />
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
import { Plus, Edit, Delete, CaretRight, Search, MoreFilled, Refresh } from "@element-plus/icons-vue"
import axios from "axios"
import { useDatasourceStore } from "@/store/datasource"

const datasourceStore = useDatasourceStore()

const loading = ref(false)
const saving = ref(false)
const reports = ref<any[]>([])
const keyword = ref("")
const quickFilter = ref("all")
const filterDatasourceId = ref<number | null>(null)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const runningId = ref<number | null>(null)

const cronPresets = [
  { label: "工作日早9点", value: "0 9 * * 1-5" },
  { label: "每天早8点", value: "0 8 * * *" },
  { label: "每周一早9点", value: "0 9 * * 1" },
  { label: "每月1号早9点", value: "0 9 1 * *" },
  { label: "每小时", value: "0 * * * *" },
]

const defaultForm = () => ({
  name: "",
  datasource_id: datasourceStore.currentId ?? null as number | null,
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
  datasource_id: [{ required: true, message: "请选择数据源", trigger: "change" }],
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
    const params = filterDatasourceId.value ? { datasource_id: filterDatasourceId.value } : {}
    const { data } = await axios.get("/api/scheduled-reports", { params })
    reports.value = data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    datasource_id: row.datasource_id,
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

onMounted(async () => {
  await datasourceStore.fetchDatasources()
  fetchReports()
})
</script>

<style scoped>
.scheduled-reports {
  padding: 0;
}

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
</style>
