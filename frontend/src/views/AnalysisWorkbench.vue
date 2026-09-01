<template>
  <div class="page analysis-workbench-page">
    <section class="workbench-topbar">
      <div>
        <p class="eyebrow">SELF-SERVICE ANALYTICS</p>
        <h2>拖拽式自助分析</h2>
        <p>基于已治理数据集配置维度、指标、筛选、排序、TopN、同环比、累计、排名、占比、钻取和联动分析。</p>
      </div>
      <div class="topbar-actions">
        <el-tooltip content="刷新数据集、分析视图和看板列表">
          <el-button :icon="Refresh" :loading="loading" @click="loadAll" />
        </el-tooltip>
        <el-button :icon="View" :loading="previewing" @click="previewView">预览</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" @click="saveView">保存分析</el-button>
      </div>
    </section>

    <section class="workbench-shell">
      <aside class="panel field-panel">
        <div class="panel-header">
          <div>
            <span>数据集</span>
            <strong>{{ currentDataset?.name || "未选择" }}</strong>
          </div>
        </div>
        <el-select v-model="form.dataset_id" filterable placeholder="选择数据集" @change="onDatasetChange">
          <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
        </el-select>
        <el-input v-model="fieldKeyword" :prefix-icon="Search" placeholder="搜索字段" clearable class="field-search" />

        <div class="field-section">
          <div class="section-title">
            <span>维度</span>
            <small>{{ filteredDimensionFields.length }}</small>
          </div>
          <div class="field-list">
            <button
              v-for="field in filteredDimensionFields"
              :key="`dimension-${field.name}`"
              class="field-card"
              type="button"
              draggable="true"
              @click="addDimension(field.name)"
              @dragstart="startDrag(field)"
            >
              <span>{{ field.label }}</span>
              <small>{{ field.type || "dimension" }}</small>
            </button>
            <el-empty v-if="!filteredDimensionFields.length" description="暂无维度" :image-size="60" class="compact-empty" />
          </div>
        </div>

        <div class="field-section">
          <div class="section-title">
            <span>指标</span>
            <small>{{ filteredMetricFields.length }}</small>
          </div>
          <div class="field-list">
            <button
              v-for="field in filteredMetricFields"
              :key="`metric-${field.name}`"
              class="field-card metric"
              type="button"
              draggable="true"
              @click="addMeasure(field.name)"
              @dragstart="startDrag(field)"
            >
              <span>{{ field.label }}</span>
              <small>{{ field.aggregation?.toUpperCase() || "SUM" }}</small>
            </button>
            <el-empty v-if="!filteredMetricFields.length" description="暂无指标" :image-size="60" class="compact-empty" />
          </div>
        </div>
      </aside>

      <main class="builder-panel">
        <section class="panel config-panel">
          <div class="config-title">
            <div>
              <span>分析配置</span>
              <strong>{{ form.name || "未命名分析" }}</strong>
            </div>
            <el-segmented v-model="form.chart_type" :options="chartOptions" @change="previewView" />
          </div>

          <div class="form-grid">
            <label>
              <span>分析名称</span>
              <el-input v-model="form.name" placeholder="例如：客户销售贡献分析" />
            </label>
            <label>
              <span>TopN</span>
              <el-input-number v-model="form.visual_config_json.top_n" :min="1" :max="5000" controls-position="right" />
            </label>
          </div>

          <div class="drop-grid">
            <section class="drop-zone" @dragover.prevent @drop="dropField('dimension')">
              <div class="drop-title">
                <span>维度</span>
                <small>分类、时间、组织等分析切片</small>
              </div>
              <div class="pill-row">
                <el-tag
                  v-for="dimension in form.dimensions"
                  :key="dimension"
                  closable
                  effect="plain"
                  @close="removeDimension(dimension)"
                >
                  {{ fieldLabel(dimension) }}
                </el-tag>
                <span v-if="!form.dimensions.length" class="drop-placeholder">拖入或点击左侧维度</span>
              </div>
            </section>

            <section class="drop-zone" @dragover.prevent @drop="dropField('measure')">
              <div class="drop-title">
                <span>指标</span>
                <small>数值字段和聚合方式</small>
              </div>
              <div class="measure-list">
                <div v-for="measure in form.measures" :key="measure.field" class="measure-row">
                  <strong>{{ fieldLabel(measure.field) }}</strong>
                  <el-select v-model="measure.aggregation" size="small" @change="previewView">
                    <el-option v-for="option in aggregationOptions" :key="option" :label="option.toUpperCase()" :value="option" />
                  </el-select>
                  <el-input v-model="measure.alias" size="small" placeholder="别名" @change="previewView" />
                  <el-button text type="danger" :icon="Delete" @click="removeMeasure(measure.field)" />
                </div>
                <span v-if="!form.measures.length" class="drop-placeholder">拖入或点击左侧指标</span>
              </div>
            </section>
          </div>

          <el-tabs v-model="activeConfigTab" class="config-tabs">
            <el-tab-pane label="筛选" name="filters">
              <div class="rule-list">
                <div v-for="(filter, index) in form.filters" :key="`filter-${index}`" class="rule-row">
                  <el-select v-model="filter.field" filterable placeholder="字段">
                    <el-option v-for="field in allFields" :key="field.name" :label="field.label" :value="field.name" />
                  </el-select>
                  <el-select v-model="filter.operator" placeholder="条件">
                    <el-option v-for="operator in filterOperators" :key="operator" :label="operator" :value="operator" />
                  </el-select>
                  <el-input v-model="filter.value" placeholder="值" @keyup.enter="previewView" />
                  <el-button text type="danger" :icon="Delete" @click="removeFilter(index)" />
                </div>
                <el-button :icon="Plus" @click="addFilter">添加筛选</el-button>
              </div>
            </el-tab-pane>

            <el-tab-pane label="排序" name="sorts">
              <div class="rule-list">
                <div v-for="(sort, index) in form.sorts" :key="`sort-${index}`" class="rule-row">
                  <el-select v-model="sort.field" filterable placeholder="字段">
                    <el-option v-for="field in sortableFields" :key="field.name" :label="field.label" :value="field.name" />
                  </el-select>
                  <el-select v-model="sort.direction" placeholder="方向">
                    <el-option label="降序" value="desc" />
                    <el-option label="升序" value="asc" />
                  </el-select>
                  <el-button text type="danger" :icon="Delete" @click="removeSort(index)" />
                </div>
                <el-button :icon="Plus" @click="addSort">添加排序</el-button>
              </div>
            </el-tab-pane>

            <el-tab-pane label="计算" name="calculations">
              <div class="calculation-grid">
                <el-checkbox-group v-model="form.calculation_fields_json.calculations" @change="previewView">
                  <el-checkbox-button label="yoy">同环比</el-checkbox-button>
                  <el-checkbox-button label="cumulative">累计</el-checkbox-button>
                  <el-checkbox-button label="rank">排名</el-checkbox-button>
                  <el-checkbox-button label="ratio">占比</el-checkbox-button>
                </el-checkbox-group>
              </div>
            </el-tab-pane>

            <el-tab-pane label="交互" name="interaction">
              <div class="interaction-grid">
                <el-switch v-model="form.interaction_json.drill" active-text="启用钻取" />
                <el-switch v-model="form.interaction_json.linkage" active-text="启用联动" />
                <el-switch v-model="form.visual_config_json.show_legend" active-text="显示图例" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </section>

        <section class="panel preview-panel">
          <div class="preview-header">
            <div>
              <span>实时预览</span>
              <strong>{{ previewTitle }}</strong>
            </div>
            <div class="preview-actions">
              <el-dropdown :disabled="!previewRows.length" @command="exportPreview">
                <el-button :icon="Download">导出</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="csv">CSV</el-dropdown-item>
                    <el-dropdown-item command="xlsx">XLSX</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button :icon="View" :loading="previewing" @click="previewView">运行预览</el-button>
            </div>
          </div>

          <el-alert v-if="errorMessage" type="error" :title="errorMessage" show-icon :closable="false" class="preview-alert" />
          <el-alert
            v-for="warning in previewWarnings"
            :key="warning"
            type="warning"
            :title="warning"
            show-icon
            :closable="false"
            class="preview-alert"
          />

          <div v-loading="previewing" class="result-surface">
            <div v-if="!previewRows.length && !previewing" class="preview-empty empty">
              <el-empty :description="hasPreviewRun ? '当前条件无数据，请调整筛选或时间范围' : '配置维度和指标后运行预览'" :image-size="88" />
            </div>
            <el-table
              v-else-if="form.chart_type === 'table'"
              :data="previewRows"
              size="small"
              height="340"
              class="result-table"
            >
              <el-table-column
                v-for="column in previewColumns"
                :key="column"
                :prop="column"
                :label="column"
                min-width="140"
                show-overflow-tooltip
              />
            </el-table>
            <div v-else ref="chartRef" class="chart-stage"></div>
          </div>

          <el-collapse v-if="previewSql" class="sql-collapse">
            <el-collapse-item title="SQL 查询计划" name="sql">
              <pre class="sql-preview">{{ previewSql }}</pre>
            </el-collapse-item>
          </el-collapse>
        </section>
      </main>

      <aside class="panel saved-panel">
        <div class="panel-header">
          <div>
            <span>已保存分析</span>
            <strong>{{ views.length }} 个视图</strong>
          </div>
        </div>
        <div class="saved-list">
          <article v-for="view in views" :key="view.id" class="saved-card" :class="{ active: view.id === form.id }">
            <button type="button" @click="loadView(view)">
              <strong>{{ view.name }}</strong>
              <span>{{ chartLabel(view.chart_type) }} · {{ datasetName(view.dataset_id) }}</span>
            </button>
            <div class="saved-actions">
              <el-tooltip content="预览">
                <el-button text :icon="View" @click="loadAndPreview(view)" />
              </el-tooltip>
              <el-tooltip content="复制">
                <el-button text :icon="CopyDocument" @click="copyAnalysisView(view)" />
              </el-tooltip>
              <el-tooltip content="发布">
                <el-button text :icon="Promotion" @click="publishAnalysisView(view)" />
              </el-tooltip>
              <el-tooltip content="加入看板">
                <el-button text :icon="Grid" @click="openDashboardDialog(view)" />
              </el-tooltip>
              <el-tooltip v-if="canDeleteAnalysis" content="删除">
                <el-button text type="danger" :icon="Delete" @click="deleteAnalysisView(view)" />
              </el-tooltip>
            </div>
          </article>
          <el-empty v-if="!views.length" description="暂无分析视图" :image-size="72" />
        </div>
      </aside>
    </section>

    <el-dialog v-model="dashboardDialogVisible" title="加入看板" width="460px">
      <div class="dashboard-dialog-body">
        <span>选择目标看板</span>
        <el-select v-model="targetDashboardId" filterable placeholder="选择看板">
          <el-option v-for="dashboard in dashboards" :key="dashboard.id" :label="dashboard.title" :value="dashboard.id" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="dashboardDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addingToDashboard" @click="addCurrentViewToDashboard">加入看板</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useAuthStore } from "@/store/auth"
import {
  Check,
  CopyDocument,
  Delete,
  Download,
  Grid,
  Plus,
  Promotion,
  Refresh,
  Search,
  View,
} from "@element-plus/icons-vue"
import * as echarts from "@/utils/echarts"
import * as XLSX from "xlsx"

type RawField = string | Record<string, any>
type DatasetItem = {
  id: number
  name: string
  fields_json?: {
    table?: string
    fields?: RawField[]
    dimensions?: RawField[]
    metrics?: RawField[]
  } | null
  aggregations_json?: { aggregations?: RawField[] } | null
  semantic_model_json?: {
    dimensions?: RawField[]
    time_dimensions?: RawField[]
    metrics?: RawField[]
    measures?: RawField[]
  } | null
}
type FieldItem = {
  name: string
  label: string
  type: string
  role: "dimension" | "metric"
  aggregation?: string
}
type MeasureItem = { field: string; aggregation: string; alias?: string }
type AnalysisView = {
  id: number
  name: string
  description?: string | null
  dataset_id: number
  chart_type: string
  dimensions: string[]
  measures: MeasureItem[]
  filters: Array<Record<string, any>>
  sorts?: Array<Record<string, any>>
  calculation_fields_json?: { calculations?: string[] } | null
  visual_config_json?: Record<string, any> | null
  interaction_json?: Record<string, any> | null
  status?: string
  visibility?: string
}
type DashboardItem = { id: number; title: string }

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const addingToDashboard = ref(false)
const fieldKeyword = ref("")
const activeConfigTab = ref("filters")
const previewSql = ref("")
const errorMessage = ref("")
const previewColumns = ref<string[]>([])
const previewRows = ref<Array<Record<string, any>>>([])
const previewWarnings = ref<string[]>([])
const chartData = ref<Record<string, any> | null>(null)
const hasPreviewRun = ref(false)
const datasets = ref<DatasetItem[]>([])
const views = ref<AnalysisView[]>([])
const dashboards = ref<DashboardItem[]>([])
const draggedField = ref<FieldItem | null>(null)
const dashboardDialogVisible = ref(false)
const targetDashboardId = ref<number | null>(null)
const dashboardViewId = ref<number | null>(null)
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let isUnmounted = false

const form = reactive({
  id: null as number | null,
  name: "",
  description: "",
  dataset_id: null as number | null,
  chart_type: "bar",
  dimensions: [] as string[],
  measures: [] as MeasureItem[],
  filters: [] as Array<Record<string, any>>,
  sorts: [] as Array<Record<string, any>>,
  calculation_fields_json: { calculations: [] as string[] },
  visual_config_json: { top_n: 20, show_legend: true } as Record<string, any>,
  interaction_json: { drill: true, linkage: true } as Record<string, any>,
})

const authStore = useAuthStore()
const canDeleteAnalysis = computed(() => authStore.isOrgAdmin)

const chartOptions = [
  { label: "柱状", value: "bar" },
  { label: "折线", value: "line" },
  { label: "面积", value: "area" },
  { label: "饼图", value: "pie" },
  { label: "散点", value: "scatter" },
  { label: "漏斗", value: "funnel" },
  { label: "表格", value: "table" },
]
const aggregationOptions = ["sum", "avg", "count", "min", "max"]
const filterOperators = ["=", "!=", ">", ">=", "<", "<=", "LIKE", "IN"]

const currentDataset = computed(() => datasets.value.find((item) => item.id === form.dataset_id) || null)
const previewTitle = computed(() => `${form.name || "未命名分析"} · ${currentDataset.value?.name || "请选择数据集"}`)

const asList = (value: unknown): RawField[] => Array.isArray(value) ? value : []
const rawName = (field: RawField) => {
  if (typeof field === "string") return field
  return String(field.field || field.name || field.key || "").trim()
}
const simpleName = (name: string) => name.includes(".") ? name.split(".").pop() || name : name
const rawLabel = (field: RawField, fallback: string) => {
  if (typeof field === "string") return simpleName(fallback)
  return String(field.alias || field.label || field.display_name || simpleName(fallback))
}
const rawType = (field: RawField) => {
  if (typeof field === "string") return "string"
  return String(field.type || field.data_type || "string")
}
const rawAggregation = (field: RawField) => {
  if (typeof field === "string") return "sum"
  return String(field.aggregation || field.fn || "sum").toLowerCase()
}
const normalizeField = (field: RawField, role: "dimension" | "metric"): FieldItem | null => {
  const name = rawName(field)
  if (!name) return null
  return {
    name: simpleName(name),
    label: rawLabel(field, name),
    type: rawType(field),
    role,
    aggregation: role === "metric" ? rawAggregation(field) : undefined,
  }
}
const dedupeFields = (fields: Array<FieldItem | null>) => {
  const seen = new Set<string>()
  return fields.filter((field): field is FieldItem => {
    if (!field || seen.has(`${field.role}:${field.name}`)) return false
    seen.add(`${field.role}:${field.name}`)
    return true
  })
}

const dimensionFields = computed(() => {
  const dataset = currentDataset.value
  if (!dataset) return []
  const fieldsJson = dataset.fields_json || {}
  const semantic = dataset.semantic_model_json || {}
  const legacyDimensions = asList(fieldsJson.fields).filter((field) => {
    if (typeof field === "string") return true
    const role = String(field.role || "").toLowerCase()
    return role !== "metric" && role !== "measure"
  })
  return dedupeFields([
    ...asList(fieldsJson.dimensions).map((field) => normalizeField(field, "dimension")),
    ...legacyDimensions.map((field) => normalizeField(field, "dimension")),
    ...asList(semantic.dimensions).map((field) => normalizeField(field, "dimension")),
    ...asList(semantic.time_dimensions).map((field) => normalizeField(field, "dimension")),
  ])
})
const metricFields = computed(() => {
  const dataset = currentDataset.value
  if (!dataset) return []
  const fieldsJson = dataset.fields_json || {}
  const aggregations = dataset.aggregations_json || {}
  const semantic = dataset.semantic_model_json || {}
  const legacyMetrics = asList(fieldsJson.fields).filter((field) => {
    if (typeof field === "string") return false
    const role = String(field.role || "").toLowerCase()
    return role === "metric" || role === "measure"
  })
  return dedupeFields([
    ...asList(fieldsJson.metrics).map((field) => normalizeField(field, "metric")),
    ...legacyMetrics.map((field) => normalizeField(field, "metric")),
    ...asList(aggregations.aggregations).map((field) => normalizeField(field, "metric")),
    ...asList(semantic.metrics).map((field) => normalizeField(field, "metric")),
    ...asList(semantic.measures).map((field) => normalizeField(field, "metric")),
  ])
})
const allFields = computed(() => [...dimensionFields.value, ...metricFields.value])
const sortableFields = computed(() => [
  ...dimensionFields.value,
  ...metricFields.value,
  ...form.measures.map((measure) => ({
    name: measure.alias || measure.field,
    label: measure.alias || fieldLabel(measure.field),
    type: "metric",
    role: "metric" as const,
  })),
])
const filteredDimensionFields = computed(() => filterFields(dimensionFields.value))
const filteredMetricFields = computed(() => filterFields(metricFields.value))

const filterFields = (fields: FieldItem[]) => {
  const keyword = fieldKeyword.value.trim().toLowerCase()
  if (!keyword) return fields
  return fields.filter((field) => [field.name, field.label, field.type].some((value) => value.toLowerCase().includes(keyword)))
}
const fieldLabel = (name: string) => allFields.value.find((field) => field.name === name)?.label || name
const datasetName = (id: number) => datasets.value.find((item) => item.id === id)?.name || `数据集 #${id}`
const chartLabel = (type: string) => chartOptions.find((item) => item.value === type)?.label || type

const loadAll = async () => {
  loading.value = true
  try {
    const [datasetResp, viewResp, dashboardResp] = await Promise.all([
      axios.get("/api/datasets"),
      axios.get("/api/analysis-views"),
      axios.get("/api/dashboards"),
    ])
    datasets.value = datasetResp.data.items || []
    views.value = viewResp.data.items || []
    dashboards.value = dashboardResp.data.items || []
    if (!form.dataset_id) form.dataset_id = datasets.value[0]?.id || null
  } catch {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

const resetPreview = () => {
  previewSql.value = ""
  previewColumns.value = []
  previewRows.value = []
  previewWarnings.value = []
  chartData.value = null
  hasPreviewRun.value = false
  errorMessage.value = ""
}
const onDatasetChange = () => {
  form.dimensions = []
  form.measures = []
  form.filters = []
  form.sorts = []
  form.id = null
  resetPreview()
}
const startDrag = (field: FieldItem) => {
  draggedField.value = field
}
const dropField = (target: "dimension" | "measure") => {
  if (!draggedField.value) return
  if (target === "dimension" && draggedField.value.role === "dimension") addDimension(draggedField.value.name)
  if (target === "measure") addMeasure(draggedField.value.name)
  draggedField.value = null
}
const addDimension = (field: string) => {
  if (!form.dimensions.includes(field)) form.dimensions.push(field)
}
const removeDimension = (field: string) => {
  form.dimensions = form.dimensions.filter((item) => item !== field)
}
const addMeasure = (field: string) => {
  if (form.measures.some((item) => item.field === field)) return
  const source = metricFields.value.find((item) => item.name === field)
  form.measures.push({
    field,
    aggregation: source?.aggregation || "sum",
    alias: source?.label && source.label !== field ? source.label : `${source?.aggregation || "sum"}_${field}`,
  })
}
const removeMeasure = (field: string) => {
  form.measures = form.measures.filter((item) => item.field !== field)
}
const addFilter = () => {
  form.filters.push({ field: allFields.value[0]?.name || "", operator: "=", value: "" })
}
const removeFilter = (index: number) => {
  form.filters.splice(index, 1)
}
const addSort = () => {
  form.sorts.push({ field: sortableFields.value[0]?.name || "", direction: "desc" })
}
const removeSort = (index: number) => {
  form.sorts.splice(index, 1)
}

const buildPayload = (limit = 200) => ({
  name: form.name,
  description: form.description,
  dataset_id: form.dataset_id,
  chart_type: form.chart_type,
  dimensions: form.dimensions,
  measures: form.measures,
  filters: form.filters.filter((item) => item.field && item.operator),
  sorts: form.sorts.filter((item) => item.field),
  calculation_fields_json: form.calculation_fields_json,
  visual_config_json: form.visual_config_json,
  interaction_json: form.interaction_json,
  visibility: "org",
  status: "draft",
  limit,
})

const previewView = async () => {
  if (!form.dataset_id) {
    ElMessage.warning("请先选择数据集")
    return
  }
  if (!form.dimensions.length && !form.measures.length) {
    ElMessage.warning("请至少选择一个维度或指标")
    return
  }
  previewing.value = true
  errorMessage.value = ""
  try {
    const { data } = await axios.post("/api/analysis-views/preview-draft", buildPayload(200))
    previewColumns.value = data.columns || []
    previewRows.value = data.rows || []
    chartData.value = data.chart_data || null
    previewSql.value = data.query_plan?.rendered_sql || data.query_plan?.sql || ""
    previewWarnings.value = data.warnings || []
    hasPreviewRun.value = true
    await renderChart()
  } catch (error: any) {
    errorMessage.value = error.response?.data?.detail || "预览失败"
    hasPreviewRun.value = true
  } finally {
    previewing.value = false
  }
}

const saveView = async () => {
  if (!form.name.trim() || !form.dataset_id) {
    ElMessage.warning("请填写分析名称并选择数据集")
    return
  }
  saving.value = true
  try {
    const payload = buildPayload(200)
    delete (payload as any).limit
    if (form.id) await axios.put(`/api/analysis-views/${form.id}`, payload)
    else {
      const { data } = await axios.post("/api/analysis-views", payload)
      form.id = data.id
    }
    ElMessage.success("分析视图已保存")
    await loadAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const loadView = (view: AnalysisView) => {
  form.id = view.id
  form.name = view.name
  form.description = view.description || ""
  form.dataset_id = view.dataset_id
  form.chart_type = view.chart_type
  form.dimensions = [...(view.dimensions || [])]
  form.measures = [...(view.measures || [])]
  form.filters = [...(view.filters || [])]
  form.sorts = [...(view.sorts || [])]
  form.calculation_fields_json = { calculations: [...(view.calculation_fields_json?.calculations || [])] }
  form.visual_config_json = { top_n: 20, show_legend: true, ...(view.visual_config_json || {}) }
  form.interaction_json = { drill: true, linkage: true, ...(view.interaction_json || {}) }
  resetPreview()
}
const loadAndPreview = async (view: AnalysisView) => {
  loadView(view)
  await nextTick()
  await previewView()
}
const copyAnalysisView = async (view?: AnalysisView) => {
  const targetId = view?.id || form.id
  if (!targetId) return
  const { data } = await axios.post(`/api/analysis-views/${targetId}/copy`)
  ElMessage.success("已复制分析视图")
  await loadAll()
  loadView(data)
}
const deleteAnalysisView = async (view: AnalysisView) => {
  try {
    await ElMessageBox.confirm(
      `确定删除分析「${view.name}」吗？此操作不可恢复。`,
      "删除确认",
      { confirmButtonText: "删除", cancelButtonText: "取消", type: "warning" }
    )
  } catch {
    return // 用户取消
  }
  try {
    await axios.delete(`/api/analysis-views/${view.id}`)
    ElMessage.success("已删除分析视图")
    if (form.id === view.id) {
      form.id = null
      resetPreview()
    }
    await loadAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "删除失败")
  }
}
const publishAnalysisView = async (view?: AnalysisView) => {
  const targetId = view?.id || form.id
  if (!targetId) return
  await axios.post(`/api/analysis-views/${targetId}/publish`, { status: "published", visibility: "org" })
  ElMessage.success("已发布到组织范围")
  await loadAll()
}
const openDashboardDialog = async (view?: AnalysisView) => {
  if (view) loadView(view)
  if (!form.id) await saveView()
  if (!form.id) return
  dashboardViewId.value = form.id
  targetDashboardId.value = dashboards.value[0]?.id || null
  dashboardDialogVisible.value = true
}
const addCurrentViewToDashboard = async () => {
  if (!dashboardViewId.value || !targetDashboardId.value) {
    ElMessage.warning("请选择目标看板")
    return
  }
  addingToDashboard.value = true
  try {
    await axios.post(`/api/analysis-views/${dashboardViewId.value}/add-to-dashboard`, {
      dashboard_id: targetDashboardId.value,
    })
    ElMessage.success("已加入看板")
    dashboardDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "加入看板失败")
  } finally {
    addingToDashboard.value = false
  }
}

const exportPreview = (type: "csv" | "xlsx") => {
  if (!previewRows.value.length) return
  const filename = `${form.name || "analysis"}-${new Date().toISOString().slice(0, 10)}`
  if (type === "xlsx") {
    const sheet = XLSX.utils.json_to_sheet(previewRows.value)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, sheet, "analysis")
    XLSX.writeFile(workbook, `${filename}.xlsx`)
    return
  }
  const header = previewColumns.value.join(",")
  const body = previewRows.value.map((row) =>
    previewColumns.value.map((column) => `"${String(row[column] ?? "").replace(/"/g, '""')}"`).join(",")
  )
  const blob = new Blob([[header, ...body].join("\n")], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `${filename}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}

const buildChartOption = () => {
  const data = chartData.value
  if (!data || !previewRows.value.length || form.chart_type === "table") return null
  const categories = data.categories || previewRows.value.map((_row, index) => String(index + 1))
  const series = data.series || []
  if (form.chart_type === "pie" || form.chart_type === "funnel") {
    const first = series[0] || { name: "值", data: [] }
    return {
      tooltip: { trigger: "item" },
      legend: form.visual_config_json.show_legend ? { top: 0 } : undefined,
      series: [{
        name: first.name,
        type: form.chart_type,
        radius: form.chart_type === "pie" ? "62%" : undefined,
        data: categories.map((name: string, index: number) => ({ name, value: Number(first.data[index]) || 0 })),
      }],
    }
  }
  if (form.chart_type === "scatter") {
    return {
      tooltip: { trigger: "item" },
      grid: { top: 24, right: 24, bottom: 44, left: 56 },
      xAxis: { type: "value", name: data.x || "" },
      yAxis: { type: "value", name: data.y || "" },
      series: [{ type: "scatter", symbolSize: 10, data: data.points || [] }],
    }
  }
  return {
    tooltip: { trigger: "axis" },
    legend: form.visual_config_json.show_legend ? { top: 0 } : undefined,
    grid: { top: form.visual_config_json.show_legend ? 42 : 20, right: 24, bottom: 48, left: 56 },
    xAxis: { type: "category", data: categories, axisLabel: { rotate: categories.length > 8 ? 35 : 0 } },
    yAxis: { type: "value" },
    series: series.map((item: any) => ({
      name: item.name,
      type: form.chart_type === "area" ? "line" : form.chart_type,
      smooth: form.chart_type === "line" || form.chart_type === "area",
      areaStyle: form.chart_type === "area" ? {} : undefined,
      data: item.data,
    })),
  }
}
const renderChart = async () => {
  await nextTick()
  // 切换标签页/路由导致组件卸载后，立即中止异步图表操作
  if (isUnmounted) return
  if (!chartRef.value || !chartRef.value.isConnected || form.chart_type === "table" || !previewRows.value.length) {
    chartInstance?.dispose()
    chartInstance = null
    return
  }
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  const option = buildChartOption()
  if (option) {
    chartInstance.clear()
    chartInstance.setOption(option)
  }
}
const resizeChart = () => {
  if (isUnmounted) return
  chartInstance?.resize()
}

watch(() => [form.chart_type, chartData.value, previewRows.value.length], () => renderChart(), { deep: true })

onMounted(loadAll)
onMounted(() => window.addEventListener("resize", resizeChart))
onBeforeUnmount(() => {
  isUnmounted = true
  window.removeEventListener("resize", resizeChart)
  chartInstance?.dispose()
})
</script>

<style scoped>
.analysis-workbench-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workbench-topbar,
.panel {
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-soft);
}

.workbench-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.workbench-topbar h2 {
  margin: 0 0 6px;
  color: var(--app-text);
  font-size: 24px;
  letter-spacing: 0;
}

.workbench-topbar p {
  margin: 0;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.topbar-actions,
.preview-actions,
.saved-actions,
.pill-row,
.interaction-grid {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workbench-shell {
  display: grid;
  grid-template-columns: 276px minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

.panel {
  padding: 14px;
}

.panel-header,
.config-title,
.preview-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-header div,
.config-title div,
.preview-header div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.panel-header span,
.config-title span,
.preview-header span,
.section-title small,
.drop-title small {
  color: var(--app-text-muted);
  font-size: 12px;
}

.panel-header strong,
.config-title strong,
.preview-header strong {
  color: var(--app-text);
  font-size: 15px;
}

.field-search {
  margin-top: 10px;
}

.field-section {
  margin-top: 16px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 700;
}

.field-list,
.saved-list,
.rule-list,
.measure-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 9px 10px;
  color: var(--app-text);
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  cursor: grab;
  transition: border-color var(--app-transition), background var(--app-transition);
}

.field-card:hover {
  background: var(--app-surface-muted);
  border-color: rgba(15, 118, 110, 0.36);
}

.field-card span {
  overflow: hidden;
  font-weight: 600;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-card small {
  flex: 0 0 auto;
  color: var(--app-text-muted);
}

.field-card.metric {
  border-color: rgba(37, 99, 235, 0.18);
}

.builder-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.config-title {
  align-items: center;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 12px;
  margin-bottom: 12px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.drop-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.drop-zone {
  min-height: 132px;
  padding: 12px;
  background: var(--app-surface-muted);
  border: 1px dashed rgba(15, 118, 110, 0.28);
  border-radius: 8px;
}

.drop-title {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 10px;
  font-weight: 700;
}

.pill-row {
  flex-wrap: wrap;
}

.drop-placeholder {
  color: var(--app-text-muted);
  font-size: 13px;
}

.measure-row,
.rule-row {
  display: grid;
  grid-template-columns: minmax(110px, 1fr) 92px minmax(120px, 1fr) 36px;
  gap: 8px;
  align-items: center;
}

.measure-row strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-row {
  grid-template-columns: minmax(130px, 1fr) 90px minmax(140px, 1fr) 36px;
}

.config-tabs {
  margin-top: 10px;
}

.calculation-grid,
.interaction-grid {
  min-height: 54px;
}

.preview-panel {
  min-height: 520px;
}

.result-surface {
  position: relative;
  min-height: 380px;
  overflow: hidden;
  background: #f8fafc;
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.chart-stage {
  width: 100%;
  height: 380px;
}

.preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 380px;
}

.preview-alert {
  margin-bottom: 10px;
}

.result-table {
  width: 100%;
}

.sql-collapse {
  margin-top: 10px;
  border: 0;
}

.sql-preview {
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: #dbeafe;
  background: #111827;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.saved-card {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: #ffffff;
}

.saved-card.active {
  border-color: rgba(15, 118, 110, 0.45);
}

.saved-card button {
  width: 100%;
  padding: 10px;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.saved-card strong,
.saved-card span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.saved-card span {
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.saved-actions {
  justify-content: flex-end;
  padding: 0 6px 6px;
}

.dashboard-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.compact-empty {
  padding: 6px 0;
}

@media (max-width: 1280px) {
  .workbench-shell {
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .saved-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .workbench-topbar,
  .topbar-actions,
  .config-title,
  .preview-header {
    align-items: stretch;
    flex-direction: column;
  }

  .workbench-shell,
  .drop-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .measure-row,
  .rule-row {
    grid-template-columns: 1fr;
  }
}
</style>
