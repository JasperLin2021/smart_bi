<template>
  <div class="governance-page datasource-page">
    <section class="governance-hero">
      <div class="governance-hero-copy">
        <p class="governance-kicker">DATA SOURCE GOVERNANCE</p>
        <h2 class="governance-title">数据源管理</h2>
        <p class="governance-desc">
          管理问数、数据集、看板和大屏共用的数据入口。优先完成连接测试、表结构配置和钻取规则，让业务用户拿到可解释的数据。
        </p>
      </div>
      <div class="governance-actions">
        <el-button :icon="Refresh" @click="fetchAll" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增数据源</el-button>
      </div>
    </section>

    <section class="governance-summary-grid">
      <div class="governance-summary-card">
        <span>全部数据源</span>
        <strong>{{ datasourceStats.total }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>已启用</span>
        <strong>{{ datasourceStats.active }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>已配置表结构</span>
        <strong>{{ datasourceStats.schemaReady }}</strong>
      </div>
      <div class="governance-summary-card">
        <span>Excel 数据源</span>
        <strong>{{ datasourceStats.excel }}</strong>
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
            placeholder="搜索名称 / 标识 / 说明"
          />
          <el-select v-model="typeFilter" clearable class="governance-filter" placeholder="数据源类型">
            <el-option label="数据库" value="database" />
            <el-option label="Excel" value="excel" />
          </el-select>
          <el-select v-model="statusFilter" clearable class="governance-filter" placeholder="启用状态">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </div>
        <div class="governance-quick-filters">
          <button
            v-for="item in datasourceQuickFilters"
            :key="item.value"
            type="button"
            class="governance-pill"
            :class="{ 'is-active': quickFilter === item.value }"
            @click="quickFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="governance-muted">共 {{ filteredDatasources.length }} 个结果</span>
      </div>

      <el-table class="governance-table" :data="filteredDatasources" v-loading="loading" row-key="id" empty-text="暂无数据源">
        <template #empty>
          <div class="governance-empty">
            <strong>还没有匹配的数据源</strong>
            <span>调整筛选条件，或新增一个 PostgreSQL / Excel 数据源后再配置表结构和钻取规则。</span>
            <el-button type="primary" :icon="Plus" @click="openCreate">新增数据源</el-button>
          </div>
        </template>
        <el-table-column label="数据源" min-width="230">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ row.name }}</strong>
              <span>{{ row.slug }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型 / 状态" width="150">
          <template #default="{ row }">
            <div class="governance-tag-row">
              <el-tag :type="row.source_type === 'excel' ? 'warning' : 'primary'" effect="plain">
                {{ sourceTypeLabel(row.source_type) }}
              </el-tag>
              <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="表结构" min-width="180">
          <template #default="{ row }">
            <div class="governance-table-name">
              <strong>{{ schemaTablesCount(row) }} 张表</strong>
              <span>{{ schemaFieldsCount(row) }} 个字段 · {{ row.drill_config ? '已配置钻取' : '未配置钻取' }}</span>
              <div class="governance-progress" :aria-label="`配置完成度 ${datasourceCompletion(row)}%`">
                <span :style="{ width: `${datasourceCompletion(row)}%` }"></span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="业务口径" min-width="260">
          <template #default="{ row }">
            <div class="governance-table-name">
              <span>{{ row.metrics_prompt ? row.metrics_prompt.substring(0, 96) : '未维护指标描述' }}</span>
              <span>{{ recommendationCount(row) }} 个推荐问题</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="370">
          <template #default="{ row }">
            <div class="governance-action-group">
              <el-button text type="primary" :icon="ViewIcon" @click="openPreview(row)">预览</el-button>
              <el-button text type="primary" :icon="Grid" @click="openSchemaModal(row)">表结构</el-button>
              <el-dropdown trigger="click">
                <el-button text :icon="MoreFilled">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :icon="Connection" @click="openDrillConfigModal(row)">配置钻取</el-dropdown-item>
                    <el-dropdown-item @click="testConnection(row.id)">测试连接</el-dropdown-item>
                    <el-dropdown-item :icon="Edit" @click="openEdit(row)">编辑数据源</el-dropdown-item>
                    <el-dropdown-item :icon="Delete" divided @click="handleDelete(row.id)">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑数据源' : '新增数据源'"
      width="min(980px, calc(100vw - 32px))"
      class="governance-modal"
      destroy-on-close
    >
      <el-form :model="form" label-position="top">
        <div class="governance-modal-shell">
          <aside class="governance-modal-rail">
            <div>
              <p class="governance-modal-title">数据源接入流程</p>
              <p class="governance-modal-copy">配置连接与语义，保存后补表结构。</p>
            </div>
            <div class="governance-modal-steps">
              <div
                v-for="(step, index) in datasourceFormSteps"
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
                <dt>类型</dt>
                <dd>{{ form.source_type === 'excel' ? 'Excel 文件' : 'PostgreSQL' }}</dd>
              </div>
              <div>
                <dt>连接</dt>
                <dd>{{ form.source_type === 'excel' ? (selectedExcelName || '未选择') : (form.database_url ? '已填写' : '未填写') }}</dd>
              </div>
              <div>
                <dt>推荐问题</dt>
                <dd>{{ recommendQuestionsText.split('\n').filter(Boolean).length }} 个</dd>
              </div>
            </dl>
            <div class="governance-modal-tip">保存后继续配置表结构。</div>
          </aside>

          <div class="governance-modal-main">
            <section class="governance-dialog-section">
              <div class="governance-section-head">
                <h3>连接信息</h3>
                <p>填写基础连接。</p>
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="名称" required>
                    <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="标识" required>
                    <el-input v-model="form.slug" placeholder="如：carsem" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="数据源类型" required>
                <el-segmented
                  v-model="form.source_type"
                  :options="[
                    { label: 'PostgreSQL', value: 'database' },
                    { label: 'Excel 文件', value: 'excel' },
                  ]"
                />
              </el-form-item>
              <el-form-item v-if="form.source_type === 'database'" label="数据库连接" required>
                <el-input
                  v-model="form.database_url"
                  placeholder="postgresql+psycopg2://user:pass@host:port/dbname"
                  type="textarea"
                  :rows="3"
                  class="code-textarea"
                />
                <div class="governance-field-hint">连接串只在保存时提交，编辑已有数据源时不会回显历史密码。</div>
              </el-form-item>
              <el-form-item v-else label="Excel 文件" required>
                <el-upload
                  drag
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  :limit="1"
                  accept=".xlsx,.xls"
                  :before-upload="preventAutoUpload"
                  :on-change="handleExcelFileChange"
                >
                  <div class="upload-content">
                    <el-icon class="upload-icon"><Upload /></el-icon>
                    <div class="upload-title">拖拽 Excel 文件到这里，或点击选择</div>
                    <div class="upload-hint">仅支持 .xlsx / .xls，保存数据源时自动上传到服务器</div>
                    <div v-if="selectedExcelName" class="upload-selected">
                      已选择：{{ selectedExcelName }}
                    </div>
                  </div>
                </el-upload>
              </el-form-item>
            </section>

            <section class="governance-dialog-section">
              <div class="governance-section-head">
                <h3>业务语义</h3>
                <p>供智能问数理解。</p>
              </div>
              <el-form-item label="指标描述">
                <el-input
                  v-model="form.metrics_prompt"
                  type="textarea"
                  :rows="4"
                  placeholder="可用的业务指标描述（可选）"
                />
                <div class="governance-field-hint">填写核心指标口径。</div>
              </el-form-item>
              <el-form-item label="推荐问题">
                <el-input
                  v-model="recommendQuestionsText"
                  type="textarea"
                  :rows="4"
                  placeholder="每行一个推荐问题（可选）"
                />
                <div class="governance-field-hint">每行一个常用问题。</div>
              </el-form-item>
            </section>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">保存后可继续配置表结构和钻取。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存数据源</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 表结构管理模态框 -->
    <SchemaMetadataModal
      v-model="schemaModalVisible"
      :datasource-id="currentDatasourceId"
      :initial-schema="currentSchema"
      @save="handleSaveSchema"
    />

    <DrillConfigModal
      v-model="drillConfigModalVisible"
      :datasource-name="currentDatasourceName"
      :config="currentDrillConfig"
      :generating="generatingDrillConfig"
      :saving="savingDrillConfig"
      @generate="handleGenerateDrillConfig"
      @save="handleSaveDrillConfig"
    />

    <el-dialog
      v-model="previewVisible"
      title="数据预览"
      width="min(1120px, calc(100vw - 32px))"
      class="preview-dialog governance-modal"
    >
      <div class="preview-shell">
        <div class="preview-overview">
          <div>
            <p class="preview-kicker">DATA PREVIEW</p>
            <h3>{{ previewDatasource?.name || '当前数据源' }}</h3>
            <span>{{ previewTableMeta?.description || '查看样例数据。' }}</span>
          </div>
          <div class="preview-stats">
            <div>
              <span>字段</span>
              <strong>{{ previewColumns.length }}</strong>
            </div>
            <div>
              <span>样例行</span>
              <strong>{{ previewRows.length }}</strong>
            </div>
          </div>
        </div>
        <div class="preview-toolbar">
          <el-select
            v-model="previewTable"
            placeholder="选择数据表"
            class="preview-table-select"
            @change="fetchPreview"
          >
            <el-option
              v-for="table in previewTables"
              :key="table.name"
              :label="table.description ? `${table.name} - ${table.description}` : table.name"
              :value="table.name"
            />
          </el-select>
          <el-button :loading="previewLoading" @click="fetchPreview">刷新</el-button>
          <span class="governance-muted">只读取前 100 行样例数据</span>
        </div>
        <el-table
          :data="previewRows"
          v-loading="previewLoading"
          border
          height="420"
          empty-text="暂无预览数据"
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
      </div>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">预览不会保存样例数据。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="previewVisible = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import type { UploadFile } from "element-plus"
import {
  Connection,
  Delete,
  Edit,
  Grid,
  MoreFilled,
  Plus,
  Refresh,
  Search,
  Upload,
  View as ViewIcon,
} from "@element-plus/icons-vue"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import SchemaMetadataModal from "@/components/SchemaMetadataModal.vue"
import DrillConfigModal from "@/components/DrillConfigModal.vue"

interface SchemaColumn {
  name: string
  type: string
  description: string | null
}

interface SchemaTable {
  name: string
  description: string | null
  columns: SchemaColumn[]
}

interface SchemaRelationship {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
}

interface SchemaMetadata {
  tables: SchemaTable[]
  relationships: SchemaRelationship[]
}

interface DrillDimension {
  id: string
  table: string
  column: string
  label: string
  kind: string
  enabled: boolean
}

interface DrillMetric {
  id: string
  table: string
  column: string
  label: string
  aggregation: string
  enabled: boolean
}

interface DrillPath {
  id: string
  source_dimension_id: string
  target_dimension_id: string
  label: string
  action: string
  enabled: boolean
}

interface DrillConfig {
  dimensions: DrillDimension[]
  metrics: DrillMetric[]
  paths: DrillPath[]
}

interface DataSourceDetail {
  id: number
  name: string
  slug: string
  source_type: string
  database_url?: string
  metadata_prompt: string
  schema_metadata: SchemaMetadata | null
  drill_config: DrillConfig | null
  metrics_prompt: string | null
  text2sql_prompt: string | null
  recommend_questions: string[] | null
  is_active: number
}

const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()

const datasources = ref<DataSourceDetail[]>([])
const loading = ref(false)
const keyword = ref("")
const typeFilter = ref("")
const statusFilter = ref<number | null>(null)
const quickFilter = ref("all")
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)
const selectedExcelFile = ref<File | null>(null)
const selectedExcelName = ref("")

// Schema modal state
const schemaModalVisible = ref(false)
const currentDatasourceId = ref<number | null>(null)
const currentSchema = ref<SchemaMetadata | null>(null)
const drillConfigModalVisible = ref(false)
const currentDatasourceName = ref("")
const currentDrillConfig = ref<DrillConfig | null>(null)
const generatingDrillConfig = ref(false)
const savingDrillConfig = ref(false)
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewDatasource = ref<DataSourceDetail | null>(null)
const previewTable = ref("")
const previewColumns = ref<string[]>([])
const previewRows = ref<Record<string, unknown>[]>([])

const previewTables = computed(() => previewDatasource.value?.schema_metadata?.tables || [])
const previewTableMeta = computed(() => previewTables.value.find(table => table.name === previewTable.value))

const datasourceFormSteps = computed(() => [
  {
    label: "命名",
    desc: "显示名和唯一标识",
    done: Boolean(form.name.trim() && form.slug.trim()),
  },
  {
    label: form.source_type === "excel" ? "上传" : "连接",
    desc: form.source_type === "excel" ? "选择 Excel 文件" : "填写连接串",
    done: form.source_type === "excel" ? Boolean(selectedExcelFile.value || isEdit.value) : Boolean(form.database_url.trim()),
  },
  {
    label: "语义",
    desc: "指标和推荐问题",
    done: Boolean(form.metrics_prompt.trim() || recommendQuestionsText.value.trim()),
  },
])

const datasourceQuickFilters = [
  { label: "全部", value: "all" },
  { label: "待补表结构", value: "missing_schema" },
  { label: "待配钻取", value: "missing_drill" },
  { label: "Excel", value: "excel" },
  { label: "已禁用", value: "disabled" },
]

const datasourceStats = computed(() => {
  const total = datasources.value.length
  const active = datasources.value.filter(item => item.is_active).length
  const excel = datasources.value.filter(item => item.source_type === "excel").length
  const schemaReady = datasources.value.filter(item => schemaTablesCount(item) > 0).length
  return { total, active, excel, schemaReady }
})

const filteredDatasources = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return datasources.value.filter(item => {
    if (quickFilter.value === "missing_schema" && schemaTablesCount(item) > 0) return false
    if (quickFilter.value === "missing_drill" && item.drill_config) return false
    if (quickFilter.value === "excel" && item.source_type !== "excel") return false
    if (quickFilter.value === "disabled" && item.is_active) return false
    if (typeFilter.value && item.source_type !== typeFilter.value) return false
    if (statusFilter.value !== null && statusFilter.value !== undefined && item.is_active !== statusFilter.value) {
      return false
    }
    if (!kw) return true
    return [item.name, item.slug, item.metadata_prompt, item.metrics_prompt]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  })
})

const form = reactive({
  name: "",
  slug: "",
  source_type: "database",
  database_url: "",
  metrics_prompt: "",
})

const recommendQuestionsText = ref("")

const fetchAll = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/datasources")
    // Fetch full details for each
    const details = await Promise.all(
      response.data.map((ds: any) => axios.get(`/api/datasources/${ds.id}`))
    )
    datasources.value = details.map(r => r.data)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据源加载失败")
  } finally {
    loading.value = false
  }
}

const sourceTypeLabel = (value: string) => value === "excel" ? "Excel" : "数据库"

const schemaTablesCount = (row: DataSourceDetail) => row.schema_metadata?.tables?.length || 0

const schemaFieldsCount = (row: DataSourceDetail) =>
  (row.schema_metadata?.tables || []).reduce((sum, table) => sum + (table.columns?.length || 0), 0)

const recommendationCount = (row: DataSourceDetail) =>
  Array.isArray(row.recommend_questions) ? row.recommend_questions.length : 0

const datasourceCompletion = (row: DataSourceDetail) => {
  let score = 20
  if (row.is_active) score += 20
  if (schemaTablesCount(row) > 0) score += 25
  if (row.drill_config) score += 20
  if (row.metrics_prompt || recommendationCount(row) > 0) score += 15
  return Math.min(score, 100)
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  form.name = ""
  form.slug = ""
  form.source_type = "database"
  form.database_url = ""
  form.metrics_prompt = ""
  selectedExcelFile.value = null
  selectedExcelName.value = ""
  recommendQuestionsText.value = ""
  dialogVisible.value = true
}

const openEdit = (row: DataSourceDetail) => {
  isEdit.value = true
  editId.value = row.id
  form.name = row.name
  form.slug = row.slug
  form.source_type = row.source_type || "database"
  form.database_url = ""  // Don't show existing URL for security
  form.metrics_prompt = row.metrics_prompt || ""
  selectedExcelFile.value = null
  selectedExcelName.value = ""
  recommendQuestionsText.value = (row.recommend_questions || []).join("\n")
  dialogVisible.value = true
}

const preventAutoUpload = () => false

const handleExcelFileChange = (uploadFile: UploadFile) => {
  const rawFile = uploadFile.raw
  if (!rawFile) {
    return
  }
  const lowerName = rawFile.name.toLowerCase()
  if (!lowerName.endsWith(".xlsx") && !lowerName.endsWith(".xls")) {
    ElMessage.warning("仅支持上传 .xlsx 或 .xls 文件")
    selectedExcelFile.value = null
    selectedExcelName.value = ""
    return
  }
  selectedExcelFile.value = rawFile
  selectedExcelName.value = rawFile.name
}

const handleSave = async () => {
  // Validate required fields
  const requiresDatabaseUrl = form.source_type === "database"
  const requiresExcelFile = form.source_type === "excel" && (!isEdit.value || !!selectedExcelFile.value)
  if (!form.name || !form.slug || (requiresDatabaseUrl && !form.database_url) || (form.source_type === "excel" && !isEdit.value && !selectedExcelFile.value)) {
    ElMessage.warning("请填写必填字段")
    return
  }

  saving.value = true
  try {
    const questions = recommendQuestionsText.value
      .split("\n")
      .map(s => s.trim())
      .filter(Boolean)

    const payload: any = {
      name: form.name,
      slug: form.slug,
      source_type: form.source_type,
      metrics_prompt: form.metrics_prompt || null,
      recommend_questions: questions.length > 0 ? questions : null,
    }

    if (form.source_type === "excel" && selectedExcelFile.value && requiresExcelFile) {
      const uploadPayload = new FormData()
      uploadPayload.append("file", selectedExcelFile.value)
      const uploadResponse = await axios.post("/api/datasources/upload-excel", uploadPayload, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      payload.database_url = uploadResponse.data.database_url
    } else if (form.database_url) {
      payload.database_url = form.database_url
    }

    if (isEdit.value && editId.value) {
      await axios.put(`/api/datasources/${editId.value}`, payload)
      ElMessage.success("数据源已更新")
    } else {
      // For new datasources, set empty metadata_prompt (will be filled via schema modal)
      payload.metadata_prompt = ""
      await axios.post("/api/datasources", payload)
      ElMessage.success("数据源已创建，请点击「表结构」按钮配置表结构")
    }

    dialogVisible.value = false
    selectedExcelFile.value = null
    selectedExcelName.value = ""
    await fetchAll()
    await datasourceStore.fetchDatasources()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除此数据源？", "提示", { type: "warning" })
    await axios.delete(`/api/datasources/${id}`)
    ElMessage.success("已删除")
    await fetchAll()
    await datasourceStore.fetchDatasources()
  } catch {
    // cancelled
  }
}

const testConnection = async (id: number) => {
  try {
    const response = await axios.post(`/api/datasources/${id}/test`)
    if (response.data.status === "ok") {
      ElMessage.success("连接成功")
    } else {
      ElMessage.error(response.data.message)
    }
  } catch {
    ElMessage.error("测试失败")
  }
}

const openPreview = async (row: DataSourceDetail) => {
  const tables = row.schema_metadata?.tables || []
  if (tables.length === 0) {
    ElMessage.warning("请先在「表结构」中检测并保存表结构")
    return
  }
  previewDatasource.value = row
  previewTable.value = tables[0].name
  previewColumns.value = []
  previewRows.value = []
  previewVisible.value = true
  await fetchPreview()
}

const fetchPreview = async () => {
  if (!previewDatasource.value || !previewTable.value) {
    return
  }
  previewLoading.value = true
  try {
    const response = await axios.get(`/api/datasources/${previewDatasource.value.id}/preview`, {
      params: { table: previewTable.value, limit: 100 },
    })
    previewColumns.value = response.data.columns || []
    previewRows.value = response.data.rows || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据预览失败")
  } finally {
    previewLoading.value = false
  }
}

const openSchemaModal = (row: DataSourceDetail) => {
  currentDatasourceId.value = row.id
  currentSchema.value = row.schema_metadata
  schemaModalVisible.value = true
}

const openDrillConfigModal = (row: DataSourceDetail) => {
  currentDatasourceId.value = row.id
  currentDatasourceName.value = row.name
  currentDrillConfig.value = row.drill_config
  drillConfigModalVisible.value = true
}

const handleSaveSchema = async (schema: SchemaMetadata) => {
  if (!currentDatasourceId.value) return
  
  try {
    // First generate the prompt from schema
    const promptResponse = await axios.post(
      `/api/datasources/${currentDatasourceId.value}/generate-prompt`,
      schema
    )
    const metadataPrompt = promptResponse.data.metadata_prompt
    
    // Save both schema_metadata and metadata_prompt
    await axios.put(`/api/datasources/${currentDatasourceId.value}`, {
      schema_metadata: schema,
      metadata_prompt: metadataPrompt
    })
    
    ElMessage.success("表结构已保存")
    schemaModalVisible.value = false
    await fetchAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  }
}

const handleGenerateDrillConfig = async () => {
  if (!currentDatasourceId.value) return

  generatingDrillConfig.value = true
  try {
    const response = await axios.post(`/api/datasources/${currentDatasourceId.value}/generate-drill-config`)
    currentDrillConfig.value = response.data
    ElMessage.success("已生成候选钻取规则")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成失败")
  } finally {
    generatingDrillConfig.value = false
  }
}

const handleSaveDrillConfig = async (config: DrillConfig) => {
  if (!currentDatasourceId.value) return

  savingDrillConfig.value = true
  try {
    await axios.put(`/api/datasources/${currentDatasourceId.value}`, {
      drill_config: config,
    })
    currentDrillConfig.value = config
    ElMessage.success("钻取规则已保存")
    drillConfigModalVisible.value = false
    await fetchAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    savingDrillConfig.value = false
  }
}

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    await authStore.fetchProfile()
  }
  await fetchAll()
})
</script>

<style scoped>
.datasource-page :deep(.el-table .cell) {
  line-height: 1.5;
}

.upload-content {
  padding: 16px 0;
  text-align: center;
}

.upload-icon {
  margin-bottom: 8px;
  color: var(--app-primary);
  font-size: 28px;
}

.upload-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}

.upload-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.upload-selected {
  margin-top: 10px;
  font-size: 13px;
  color: var(--app-primary);
}

.preview-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  padding: 0 20px 14px;
  margin-bottom: 12px;
}

.preview-shell {
  padding-top: 20px;
}

.preview-overview {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin: 0 20px 16px;
  padding: 16px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.preview-kicker {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.preview-overview h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
}

.preview-overview span {
  display: block;
  margin-top: 6px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.preview-stats {
  display: grid;
  grid-template-columns: repeat(2, 88px);
  gap: 10px;
  flex-shrink: 0;
}

.preview-stats div {
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.preview-stats span {
  margin: 0 0 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.preview-stats strong {
  color: var(--app-text);
  font-size: 18px;
}

.preview-dialog :deep(.el-table) {
  margin: 0 20px 20px;
  width: calc(100% - 40px);
}

.preview-table-select {
  width: 280px;
}

.truncate-text {
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.code-textarea :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

@media (max-width: 640px) {
  .preview-overview {
    flex-direction: column;
  }

  .preview-stats {
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .preview-table-select {
    width: 100%;
  }
}
</style>
