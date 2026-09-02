<template>
  <div class="page report-center-page">
    <section class="enterprise-hero">
      <div>
        <p class="eyebrow">ENTERPRISE REPORTING</p>
        <h2>复杂报表中心</h2>
        <p>沉淀类 Excel 格子报表、参数报表、主子报表、交叉报表和填报模板，统一版本、导出和分发。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建复杂报表</el-button>
      </div>
    </section>

    <section class="report-summary">
      <div class="summary-tile">
        <span>报表模板</span>
        <strong>{{ reports.length }}</strong>
        <small>{{ publishedCount }} 个已发布</small>
      </div>
      <div class="summary-tile">
        <span>填报模板</span>
        <strong>{{ fillFormCount }}</strong>
        <small>支持校验与写回审计</small>
      </div>
      <div class="summary-tile">
        <span>高保真导出</span>
        <strong>Excel / PDF / Word</strong>
        <small>导出任务可追踪</small>
      </div>
      <div class="summary-tile">
        <span>版本管理</span>
        <strong>v{{ latestVersion }}</strong>
        <small>模板更新自动留痕</small>
      </div>
    </section>

    <el-card shadow="never" class="enterprise-workbench">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索报表名称 / 类型" />
          <el-select v-model="datasetFilter" clearable placeholder="全部数据集">
            <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
          </el-select>
        </div>
        <span class="muted">共 {{ filteredReports.length }} 个模板</span>
      </div>

      <el-table :data="filteredReports" v-loading="loading" row-key="id" empty-text="暂无复杂报表模板">
        <el-table-column label="报表" min-width="260">
          <template #default="{ row }">
            <div class="name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.dataset_id ? datasetName(row.dataset_id) : "AI 生成" }} · {{ reportTypeLabel(row.report_type) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="能力标签" min-width="260">
          <template #default="{ row }">
            <div class="tag-row">
              <el-tag size="small" effect="plain">类 Excel</el-tag>
              <el-tag v-if="row.parameter_schema_json" size="small" type="success" effect="plain">参数报表</el-tag>
              <el-tag v-if="row.binding_json" size="small" type="warning" effect="plain">数据绑定</el-tag>
              <el-tag v-if="row.fill_schema_json" size="small" type="danger" effect="plain">数据填报</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.status === "published" ? "已发布" : "草稿" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="90">
          <template #default="{ row }">v{{ row.version }}</template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="150">
          <template #default="{ row }">{{ formatDate(row.updated_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <div class="icon-actions">
              <template v-if="row.report_type === 'ai_html'">
                <el-tooltip content="预览报表">
                  <el-button :icon="View" circle :loading="previewLoadingId === row.id" @click="openAiPreview(row)" />
                </el-tooltip>
                <el-tooltip content="下载 HTML 文件">
                  <el-button :icon="Download" circle :loading="isExporting(row, 'html')" @click="exportReport(row, 'html')" />
                </el-tooltip>
              </template>
              <template v-else>
                <el-tooltip content="预览设计器">
                  <el-button :icon="View" circle @click="openDesigner(row)" />
                </el-tooltip>
                <el-tooltip content="编辑模板">
                  <el-button :icon="Edit" circle @click="openDesigner(row)" />
                </el-tooltip>
                <el-dropdown trigger="click" @command="(type: string) => exportReport(row, type)">
                  <el-button circle :loading="isExporting(row, '')" :icon="Download" aria-label="导出报表" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="excel">导出 Excel</el-dropdown-item>
                      <el-dropdown-item command="pdf">导出 PDF</el-dropdown-item>
                      <el-dropdown-item command="word">导出 Word</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
              <el-tooltip content="导出记录">
                <el-button :icon="Tickets" circle @click="openRunsDrawer(row)" />
              </el-tooltip>
              <el-tooltip v-if="canDeleteReport" content="删除报表">
                <el-button text type="danger" :icon="Delete" aria-label="删除报表" @click="deleteReport(row)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="previewVisible" :title="previewTitle || 'AI 报表预览'" width="min(1100px, calc(100vw - 32px))" destroy-on-close>
      <iframe
        v-if="previewHtml"
        class="ai-html-preview-frame"
        sandbox="allow-scripts"
        :srcdoc="previewHtml"
        title="AI 报表预览"
      ></iframe>
      <el-empty v-else description="该模板没有可预览的 HTML 内容" />
    </el-dialog>

    <el-drawer v-model="runsVisible" :title="runsTitle" size="min(560px, 100vw)">
      <div v-loading="runsLoading" class="runs-drawer">
        <div class="runs-toolbar">
          <el-dropdown v-if="runsTemplate?.report_type !== 'ai_html'" trigger="click" @command="(type: string) => quickExport(type)">
            <el-button type="primary" :icon="Download" :loading="Boolean(exportingId)">导出报表</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="excel">导出 Excel</el-dropdown-item>
                <el-dropdown-item command="pdf">导出 PDF</el-dropdown-item>
                <el-dropdown-item command="word">导出 Word</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button
            v-else
            type="primary"
            :icon="Download"
            :loading="Boolean(exportingId)"
            @click="runsTemplate && exportReport(runsTemplate, 'html')"
          >
            下载 HTML
          </el-button>
          <span class="muted">最近 100 条导出记录</span>
        </div>
        <el-empty v-if="!runsLoading && runsList.length === 0" description="暂无导出记录" :image-size="80" />
        <div v-else class="run-list">
          <div v-for="item in runsList" :key="item.id" class="run-item">
            <div class="run-item-main">
              <div class="run-item-title">
                <strong>{{ formatExportType(item.export_type) }} 导出 · v{{ item.version || 1 }}</strong>
                <el-tag :type="runStatusType(item.status)" size="small" effect="plain">
                  {{ runStatusLabel(item.status) }}
                </el-tag>
              </div>
              <p v-if="item.content_preview" class="run-item-preview">{{ item.content_preview }}</p>
              <p v-if="item.error_message" class="run-item-error" :title="item.error_message">{{ item.error_message }}</p>
              <span class="run-item-time">{{ formatDate(item.finished_at || item.started_at) }}</span>
            </div>
            <el-button
              v-if="item.status === 'completed' && item.output_uri"
              text
              type="primary"
              :loading="runsDownloadingId === item.id"
              :disabled="Boolean(runsDownloadingId)"
              @click="downloadRun(item)"
            >
              下载
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="dialogVisible" title="新建复杂报表" width="min(760px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="报表名称">
              <el-input v-model="form.name" placeholder="例：Nova OEE 周报" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="绑定数据集">
              <el-select v-model="form.dataset_id" placeholder="选择数据集" style="width: 100%">
                <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="报表类型">
              <el-select v-model="form.report_type" style="width: 100%">
                <el-option label="分页报表" value="paginated" />
                <el-option label="参数报表" value="parameterized" />
                <el-option label="主子报表" value="master_detail" />
                <el-option label="交叉报表" value="cross_tab" />
                <el-option label="填报报表" value="fill_form" />
                <el-option label="Word 报告" value="word" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="可见范围">
              <el-segmented v-model="form.visibility" :options="visibilityOptions" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="说明报表用途、分发对象或填报场景" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTemplate">保存并进入设计器</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useAuthStore } from "@/store/auth"
import { Delete, Download, Edit, Plus, Refresh, Search, Tickets, View } from "@element-plus/icons-vue"
import { saveAs } from "file-saver"

type DatasetItem = { id: number; name: string }
type ReportTemplate = {
  id: number
  name: string
  description?: string | null
  dataset_id: number
  report_type: string
  status: string
  visibility: string
  version: number
  layout_json?: { kind?: string; html?: string } | null
  parameter_schema_json?: Record<string, unknown> | null
  binding_json?: Record<string, unknown> | null
  fill_schema_json?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

type ExportRunItem = {
  id: number
  template_id: number
  version?: number | null
  run_type: string
  export_type?: string | null
  status: string
  output_uri?: string | null
  content_preview?: string | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
}

const router = useRouter()
const authStore = useAuthStore()
const canDeleteReport = computed(() => authStore.isOrgAdmin)
const loading = ref(false)
const saving = ref(false)
const exportingId = ref("")
const runsVisible = ref(false)
const runsLoading = ref(false)
const runsList = ref<ExportRunItem[]>([])
const runsTemplate = ref<ReportTemplate | null>(null)
const runsDownloadingId = ref<number | null>(null)
const dialogVisible = ref(false)
const keyword = ref("")
const datasetFilter = ref<number | null>(null)
const reports = ref<ReportTemplate[]>([])
const datasets = ref<DatasetItem[]>([])
const visibilityOptions = [
  { label: "仅自己", value: "private" },
  { label: "组织可见", value: "org" },
]

const form = reactive({
  name: "",
  description: "",
  dataset_id: null as number | null,
  report_type: "paginated",
  visibility: "org",
})

const publishedCount = computed(() => reports.value.filter((item) => item.status === "published").length)
const fillFormCount = computed(() => reports.value.filter((item) => item.report_type === "fill_form" || item.fill_schema_json).length)
const latestVersion = computed(() => reports.value.reduce((max, item) => Math.max(max, item.version || 1), 1))
const filteredReports = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return reports.value.filter((item) => {
    const matchKeyword = !text || `${item.name} ${item.report_type}`.toLowerCase().includes(text)
    const matchDataset = !datasetFilter.value || item.dataset_id === datasetFilter.value
    return matchKeyword && matchDataset
  })
})

const reportTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    paginated: "分页报表",
    parameterized: "参数报表",
    master_detail: "主子报表",
    cross_tab: "交叉报表",
    fill_form: "填报报表",
    word: "Word 报告",
    ai_html: "AI 报表",
  }
  return labels[type] || type
}

const datasetName = (id: number) => datasets.value.find((item) => item.id === id)?.name || `数据集 #${id}`

const formatDate = (value?: string | null) => {
  if (!value) return "-"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false })
}

const loadAll = async () => {
  loading.value = true
  try {
    const [reportResp, datasetResp] = await Promise.all([
      axios.get("/api/report-templates"),
      axios.get("/api/datasets"),
    ])
    reports.value = reportResp.data.items || []
    datasets.value = datasetResp.data.items || []
  } catch {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  form.name = ""
  form.description = ""
  form.dataset_id = datasets.value[0]?.id || null
  form.report_type = "paginated"
  form.visibility = "org"
  dialogVisible.value = true
}

const saveTemplate = async () => {
  if (!form.name.trim() || !form.dataset_id) {
    ElMessage.warning("请填写报表名称并选择数据集")
    return
  }
  saving.value = true
  try {
    const { data } = await axios.post("/api/report-templates", {
      ...form,
      dataset_id: form.dataset_id,
      layout_json: { paper: "A4", cells: [{ row: 1, col: 1, value: form.name }] },
      parameter_schema_json: form.report_type === "parameterized" ? { date_range: { type: "date_range", label: "日期范围" } } : null,
      binding_json: { bands: [{ dataset_id: form.dataset_id, repeat: "detail" }] },
      fill_schema_json: form.report_type === "fill_form" ? { fields: [{ name: "comment", label: "填报说明", required: true }] } : null,
    })
    ElMessage.success("复杂报表已创建")
    dialogVisible.value = false
    await loadAll()
    router.push(`/report-designer/${data.id}`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const openDesigner = (row: ReportTemplate) => {
  router.push(`/report-designer/${row.id}`)
}

const previewVisible = ref(false)
const previewLoadingId = ref<number | null>(null)
const previewTitle = ref("")
const previewHtml = ref("")

const openAiPreview = async (row: ReportTemplate) => {
  previewLoadingId.value = row.id
  try {
    const { data } = await axios.get(`/api/report-templates/${row.id}`)
    previewTitle.value = data.name || row.name
    previewHtml.value = data.layout_json?.html || ""
    previewVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "加载预览失败")
  } finally {
    previewLoadingId.value = null
  }
}

const exportFormats: Record<string, { label: string; ext: string }> = {
  excel: { label: "Excel", ext: "xlsx" },
  pdf: { label: "PDF", ext: "pdf" },
  word: { label: "Word", ext: "docx" },
  html: { label: "HTML", ext: "html" },
}

const formatExportType = (type?: string | null) => (type ? exportFormats[type]?.label || type : "—")

const runStatusLabel = (status: string) =>
  ({ completed: "成功", failed: "失败", running: "处理中", queued: "排队中" } as Record<string, string>)[status] || status

const runStatusType = (status: string) =>
  ({ completed: "success", failed: "danger", running: "warning", queued: "info" } as Record<string, string>)[status] || "info"

const isExporting = (row: ReportTemplate, exportType: string) =>
  exportType ? exportingId.value === `${row.id}:${exportType}` : exportingId.value.startsWith(`${row.id}:`)

const friendlyFileName = (row: ReportTemplate, exportType: string) => {
  const base = (row.name || "报表").replace(/[\\/:*?"<>|]/g, "_").trim() || "report"
  const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "")
  const ext = exportFormats[exportType]?.ext || "bin"
  return `${base}-v${row.version || 1}-${stamp}.${ext}`
}

const fetchRunBlob = async (runId: number): Promise<Blob> => {
  // blob 请求仍需携带 Bearer Token；错误体也是 Blob，交给 blobErrorMessage 解析。
  const { data } = await axios.get(`/api/report-templates/runs/${runId}/download`, {
    responseType: "blob",
    suppressGlobalError: true,
  } as any)
  return data as Blob
}

const blobErrorMessage = async (error: unknown): Promise<string | null> => {
  const axiosError = error as { response?: { data?: unknown }; message?: string } | null
  const responseData = axiosError?.response?.data
  if (responseData instanceof Blob) {
    try {
      const parsed = JSON.parse(await responseData.text()) as { detail?: string; message?: string }
      return parsed?.detail || parsed?.message || "下载失败"
    } catch {
      return "下载失败"
    }
  }
  return (responseData as { detail?: string } | undefined)?.detail || axiosError?.message || null
}

const exportReport = async (row: ReportTemplate, exportType: string) => {
  if (!exportFormats[exportType]) {
    ElMessage.warning("不支持的导出格式")
    return
  }
  exportingId.value = `${row.id}:${exportType}`
  try {
    const { data } = await axios.post(`/api/report-templates/${row.id}/export`, {
      export_type: exportType,
      parameters: {},
    })
    if (data.status !== "completed" || !data.run_id) {
      throw new Error(data.message || "导出任务未完成，请稍后在「导出记录」中下载")
    }
    const blob = await fetchRunBlob(data.run_id)
    saveAs(blob, friendlyFileName(row, exportType))
    ElMessage.success(`${formatExportType(exportType)} 报表已生成并开始下载`)
  } catch (error) {
    const message = await blobErrorMessage(error)
    ElMessage.error(message || "导出失败")
  } finally {
    exportingId.value = ""
    if (runsVisible.value && runsTemplate.value?.id === row.id) {
      await loadRuns()
    }
  }
}

const runsTitle = computed(() => (runsTemplate.value ? `导出记录 · ${runsTemplate.value.name}` : "导出记录"))

const openRunsDrawer = async (row: ReportTemplate) => {
  runsTemplate.value = row
  runsVisible.value = true
  await loadRuns()
}

const loadRuns = async () => {
  const template = runsTemplate.value
  if (!template) return
  runsLoading.value = true
  try {
    const { data } = await axios.get(`/api/report-templates/${template.id}/runs`)
    runsList.value = Array.isArray(data) ? data : data.items || []
  } catch {
    runsList.value = []
  } finally {
    runsLoading.value = false
  }
}

const quickExport = (exportType: string) => {
  if (runsTemplate.value) void exportReport(runsTemplate.value, exportType)
}

const extFromUri = (uri?: string | null) => {
  const matched = /\.(\w+)$/.exec(uri || "")
  return matched ? matched[1] : "bin"
}

const downloadRun = async (item: ExportRunItem) => {
  runsDownloadingId.value = item.id
  try {
    const blob = await fetchRunBlob(item.id)
    const base = ((runsTemplate.value?.name || "报表") + `-run${item.id}`).replace(/[\\/:*?"<>|]/g, "_")
    saveAs(blob, `${base}.${extFromUri(item.output_uri)}`)
    ElMessage.success("文件已开始下载")
  } catch (error) {
    const message = await blobErrorMessage(error)
    ElMessage.error(message || "下载失败")
  } finally {
    runsDownloadingId.value = null
  }
}

const deleteReport = async (row: ReportTemplate) => {
  try {
    await ElMessageBox.confirm(
      `确定删除复杂报表「${row.name}」吗？此操作不可恢复，关联的填报记录、运行记录与历史版本将一并删除。`,
      "删除确认",
      { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
    )
  } catch {
    return // 用户取消
  }
  try {
    await axios.delete(`/api/report-templates/${row.id}`)
    ElMessage.success("复杂报表已删除")
    await loadAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "删除失败")
  }
}

onMounted(loadAll)
</script>

<style scoped>
.report-center-page {
  gap: 16px;
}

.enterprise-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.enterprise-hero h2 {
  margin: 4px 0 8px;
  font-size: 24px;
  letter-spacing: 0;
}

.enterprise-hero p {
  margin: 0;
  max-width: 720px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.hero-actions,
.toolbar,
.toolbar-left,
.tag-row,
.icon-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-tile {
  min-height: 96px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.summary-tile span,
.summary-tile small,
.muted,
.name-cell span {
  color: var(--app-text-muted);
}

.summary-tile strong {
  display: block;
  margin: 8px 0 4px;
  font-size: 22px;
  color: var(--app-text);
}

.enterprise-workbench {
  min-height: 420px;
}

.toolbar {
  justify-content: space-between;
  margin-bottom: 14px;
}

.toolbar-left .el-input {
  width: 260px;
}

.toolbar-left .el-select {
  width: 220px;
}

.name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.icon-actions :deep(.el-button) {
  width: 34px;
  height: 34px;
}

.ai-html-preview-frame {
  width: 100%;
  height: min(72vh, 760px);
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: #ffffff;
}

.runs-drawer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.runs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.runs-toolbar .muted {
  font-size: 12px;
}

.run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
}

.run-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.run-item-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.run-item-preview {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.run-item-error {
  margin: 0;
  color: var(--app-danger);
  font-size: 12px;
  line-height: 1.5;
}

.run-item-time {
  color: var(--app-text-light);
  font-size: 12px;
}

@media (max-width: 900px) {
  .enterprise-hero,
  .toolbar,
  .toolbar-left {
    align-items: stretch;
    flex-direction: column;
  }

  .report-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-left .el-input,
  .toolbar-left .el-select {
    width: 100%;
  }
}
</style>
