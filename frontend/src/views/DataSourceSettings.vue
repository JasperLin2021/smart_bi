<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-header-title">数据源管理</span>
              <el-button type="primary" size="small" @click="openCreate">新增数据源</el-button>
            </div>
          </template>

          <el-table :data="datasources" stripe>
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="slug" label="标识" width="120" />
            <el-table-column prop="source_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.source_type === 'excel' ? 'warning' : 'primary'" size="small">
                  {{ row.source_type === 'excel' ? 'Excel' : '数据库' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="元数据提示词" min-width="200">
              <template #default="{ row }">
                <span class="truncate-text">{{ row.metadata_prompt?.substring(0, 80) }}...</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openSchemaModal(row)">表结构</el-button>
                <el-button size="small" @click="openDrillConfigModal(row)">钻取</el-button>
                <el-button size="small" @click="testConnection(row.id)">测试连接</el-button>
                <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑数据源' : '新增数据源'" width="700px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
        </el-form-item>
        <el-form-item label="标识 (slug)" required>
          <el-input v-model="form.slug" placeholder="如：carsem（英文标识，URL友好）" />
        </el-form-item>
        <el-form-item label="数据源类型" required>
          <el-select v-model="form.source_type" placeholder="选择类型" style="width: 100%">
            <el-option label="PostgreSQL" value="database" />
            <el-option label="Excel 文件" value="excel" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.source_type === 'database'" label="数据库连接" required>
          <el-input
            v-model="form.database_url"
            placeholder="postgresql+psycopg2://user:pass@host:port/dbname"
            type="textarea"
            :rows="2"
          />
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
              <div class="upload-title">拖拽 Excel 文件到这里，或点击选择</div>
              <div class="upload-hint">仅支持 .xlsx / .xls，保存数据源时自动上传到服务器</div>
              <div v-if="selectedExcelName" class="upload-selected">
                已选择：{{ selectedExcelName }}
              </div>
            </div>
          </el-upload>
        </el-form-item>
        <el-form-item label="指标描述">
          <el-input
            v-model="form.metrics_prompt"
            type="textarea"
            :rows="3"
            placeholder="可用的业务指标描述（可选）"
          />
        </el-form-item>
        <el-form-item label="推荐问题">
          <el-input
            v-model="recommendQuestionsText"
            type="textarea"
            :rows="3"
            placeholder="每行一个推荐问题（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import type { UploadFile } from "element-plus"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import { useRouter } from "vue-router"
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
const router = useRouter()

const datasources = ref<DataSourceDetail[]>([])
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

const form = reactive({
  name: "",
  slug: "",
  source_type: "database",
  database_url: "",
  metrics_prompt: "",
})

const recommendQuestionsText = ref("")

const fetchAll = async () => {
  const response = await axios.get("/api/datasources")
  // Fetch full details for each
  const details = await Promise.all(
    response.data.map((ds: any) => axios.get(`/api/datasources/${ds.id}`))
  )
  datasources.value = details.map(r => r.data)
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
.upload-content {
  padding: 8px 0;
  text-align: center;
}

.upload-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.upload-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.upload-selected {
  margin-top: 10px;
  font-size: 13px;
  color: #409eff;
}
</style>

<style scoped>
.page :deep(.el-card) {
  border: none;
  box-shadow: var(--app-shadow-soft);
}

.page :deep(.el-card:hover) {
  transform: none;
}

.page :deep(.el-card__header) {
  padding: 20px 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-title {
  font-weight: 600;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header-title::before {
  content: '';
  width: 4px;
  height: 18px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 2px;
}

.page :deep(.el-table) {
  --el-table-border-color: var(--app-border-light);
}

.page :deep(.el-table th) {
  background: var(--app-surface-muted) !important;
  font-weight: 600;
  color: var(--app-text);
}

.page :deep(.el-table td) {
  padding: 14px 12px;
}

.page :deep(.el-table .el-button) {
  padding: 6px 12px;
}

.truncate-text {
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

/* Dialog styling */
:deep(.el-dialog) {
  border-radius: var(--app-radius);
}

:deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid var(--app-border-light);
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid var(--app-border-light);
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
