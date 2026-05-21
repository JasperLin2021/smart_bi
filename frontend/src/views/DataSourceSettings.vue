<template>
  <div class="governance-page datasource-page">
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
        <el-button type="primary" :icon="Plus" @click="openCreate">新增数据源</el-button>
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
            placeholder="搜索名称 / 标识 / 说明"
          />
          <el-select v-model="typeFilter" clearable class="governance-filter" placeholder="数据源类型">
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="MySQL" value="mysql" />
            <el-option label="ClickHouse" value="clickhouse" />
            <el-option label="SQL Server" value="mssql" />
            <el-option label="SQLite" value="sqlite" />
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

      <el-table class="governance-table" :data="filteredDatasources" v-loading="loading" row-key="id" empty-text="暂无数据源"
        highlight-current-row style="cursor:pointer"
        @row-click="(row: any, _c: any, e: MouseEvent) => { if (!(e.target as HTMLElement).closest('.el-button,.el-switch,.el-dropdown')) openDetail(row) }"
      >
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
                    <el-dropdown-item @click="openRlsModal(row)">行级权限 (RLS)</el-dropdown-item>
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

    <!-- Detail Modal -->
    <el-dialog v-model="detailVisible" width="580px" destroy-on-close class="governance-modal">
      <template #header>
        <div class="detail-modal-header" v-if="detailRow">
          <div class="detail-modal-icon" :class="`ds-icon--${detailRow.source_type}`">
            {{ detailRow.source_type?.toUpperCase().slice(0,2) }}
          </div>
          <div>
            <div class="detail-modal-title">{{ detailRow.name }}</div>
            <div class="detail-modal-sub">{{ detailRow.slug }}</div>
          </div>
          <el-tag :type="detailRow.is_active ? 'success' : 'info'" effect="plain" size="small" style="margin-left:auto">
            {{ detailRow.is_active ? '启用' : '禁用' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="类型">
          <el-tag :type="detailRow.source_type === 'excel' ? 'warning' : 'primary'" effect="plain" size="small">
            {{ sourceTypeLabel(detailRow.source_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="表结构">
          {{ schemaTablesCount(detailRow) }} 张表 · {{ schemaFieldsCount(detailRow) }} 个字段
        </el-descriptions-item>
        <el-descriptions-item label="钻取规则">{{ detailRow.drill_config ? '已配置' : '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="推荐问题">{{ recommendationCount(detailRow) }} 个</el-descriptions-item>
        <el-descriptions-item v-if="detailRow.metrics_prompt" label="业务口径" :span="2">
          <span class="detail-text-clamp">{{ detailRow.metrics_prompt }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button @click="testConnection(detailRow!.id); detailVisible = false">测试连接</el-button>
        <el-button type="primary" @click="openEdit(detailRow!); detailVisible = false">编辑</el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑数据源' : '新增数据源'"
      width="min(980px, calc(100vw - 32px))"
      class="governance-modal"
      destroy-on-close
    >
      <el-form :model="form" label-position="top">
        <el-tabs v-model="dialogActiveTab" class="modal-tabs">
          <el-tab-pane label="连接信息" name="connect">
            <div class="modal-tab-content">
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
              <el-form-item label="连接器类型" required>
                <div class="connector-type-grid">
                  <button v-for="ct in connectorTypes" :key="ct.value" type="button" class="connector-type-card" :class="{ 'is-active': form.source_type === ct.value }" @click="selectConnectorType(ct.value)">
                    <span class="connector-icon">{{ ct.icon }}</span>
                    <span class="connector-label">{{ ct.label }}</span>
                  </button>
                </div>
              </el-form-item>
              <template v-if="isDbConnector && form.source_type !== 'sqlite'">
                <el-row :gutter="16">
                  <el-col :xs="24" :md="14">
                    <el-form-item label="主机地址" required>
                      <el-input v-model="form.conn_host" placeholder="localhost 或 IP" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="10">
                    <el-form-item label="端口" required>
                      <el-input v-model="form.conn_port" placeholder="端口号" />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item label="数据库名" required>
                  <el-input v-model="form.conn_db" placeholder="数据库名称" />
                </el-form-item>
                <el-row :gutter="16">
                  <el-col :xs="24" :md="12">
                    <el-form-item label="用户名" required>
                      <el-input v-model="form.conn_user" placeholder="用户名" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :md="12">
                    <el-form-item label="密码">
                      <el-input v-model="form.conn_password" type="password" placeholder="密码" show-password />
                    </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item>
                  <el-checkbox v-model="form.conn_advanced">高级：直接编辑连接串</el-checkbox>
                </el-form-item>
                <el-form-item v-if="form.conn_advanced" label="连接串">
                  <el-input v-model="form.database_url" type="textarea" :rows="2" class="code-textarea" :placeholder="urlPlaceholder" />
                  <div class="governance-field-hint">手动填写后将覆盖上方表单生成的连接串。</div>
                </el-form-item>
                <div v-else-if="generatedUrl" class="connector-url-preview">
                  <span class="url-preview-label">连接串预览</span>
                  <code class="url-preview-value">{{ maskedUrl }}</code>
                </div>
                <div v-if="!isEdit" class="governance-field-hint">密码只在保存时提交，编辑已有数据源时需重新填写。</div>
              </template>
              <el-form-item v-else-if="form.source_type === 'sqlite'" label="数据库文件路径" required>
                <el-input v-model="form.conn_sqlite_path" placeholder="/data/mydb.sqlite" />
                <div class="governance-field-hint">服务器上的绝对路径。</div>
              </el-form-item>
              <el-form-item v-else-if="form.source_type === 'excel'" label="Excel 文件" required>
                <el-upload drag action="#" :auto-upload="false" :show-file-list="false" :limit="1" accept=".xlsx,.xls" :before-upload="preventAutoUpload" :on-change="handleExcelFileChange">
                  <div class="upload-content">
                    <el-icon class="upload-icon"><Upload /></el-icon>
                    <div class="upload-title">拖拽 Excel 文件到这里，或点击选择</div>
                    <div class="upload-hint">仅支持 .xlsx / .xls，保存数据源时自动上传到服务器</div>
                    <div v-if="selectedExcelName" class="upload-selected">已选择：{{ selectedExcelName }}</div>
                  </div>
                </el-upload>
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="业务语义" name="semantic">
            <div class="modal-tab-content">
              <el-form-item label="指标描述">
                <el-input v-model="form.metrics_prompt" type="textarea" :rows="5" placeholder="可用的业务指标描述（可选）" />
                <div class="governance-field-hint">填写核心指标口径，智能问数时会参考。</div>
              </el-form-item>
              <el-form-item>
                <template #label>
                  <div class="semantic-label-row">
                    <span>推荐问题</span>
                    <el-button
                      size="small"
                      type="primary"
                      plain
                      :icon="MagicStick"
                      :loading="generatingRecommendQuestions"
                      :disabled="!isEdit || !editId"
                      @click="generateRecommendQuestions"
                    >
                      AI 生成
                    </el-button>
                  </div>
                </template>
                <el-input v-model="recommendQuestionsText" type="textarea" :rows="5" placeholder="每行一个推荐问题（可选）" />
                <div class="governance-field-hint">每行一个常用问题，显示在问数入口。新增数据源需先保存后再生成。</div>
              </el-form-item>
            </div>
          </el-tab-pane>
        </el-tabs>
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

    <!-- RLS 管理对话框 -->
    <el-dialog
      v-model="rlsModalVisible"
      title="行级权限（Row-Level Security）"
      width="min(900px, calc(100vw - 32px))"
      class="governance-modal"
      destroy-on-close
    >
      <div class="rls-shell">
        <div class="rls-intro">
          <p>为不同<strong>组织</strong>或<strong>用户</strong>设置数据过滤规则，查询时自动注入 WHERE 条件，限制可见数据范围。</p>
        </div>

        <el-table :data="rlsRules" size="small" border v-loading="rlsLoading" empty-text="暂无规则">
          <el-table-column label="表名" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.table_name" size="small" placeholder="表名" />
            </template>
          </el-table-column>
          <el-table-column label="字段" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.column_name" size="small" placeholder="字段名" />
            </template>
          </el-table-column>
          <el-table-column label="操作符" width="120">
            <template #default="{ row }">
              <el-select v-model="row.operator" size="small" style="width:100%">
                <el-option v-for="op in rlsOperators" :key="op" :label="op" :value="op" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="过滤值" min-width="140">
            <template #default="{ row }">
              <el-input v-model="row.filter_value" size="small" placeholder="过滤值（IN 用逗号分隔）" />
            </template>
          </el-table-column>
          <el-table-column label="作用范围" min-width="160">
            <template #default="{ row }">
              <div class="rls-scope">
                <el-select v-model="row._scopeType" size="small" style="width:90px" @change="row.org_id=null;row.user_id=null">
                  <el-option label="组织" value="org" />
                  <el-option label="用户" value="user" />
                </el-select>
                <el-input v-model.number="row.org_id" v-if="row._scopeType === 'org'" size="small" placeholder="org_id" type="number" style="width:70px" />
                <el-input v-model.number="row.user_id" v-else size="small" placeholder="user_id" type="number" style="width:70px" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="60" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" :active-value="1" :inactive-value="0" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button v-if="row.id" text type="primary" size="small" :loading="row._saving" @click="saveRlsRule(row)">保存</el-button>
              <el-button v-else text type="success" size="small" :loading="row._saving" @click="createRlsRule(row)">创建</el-button>
              <el-button text type="danger" size="small" @click="deleteRlsRule(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="rls-toolbar">
          <el-button :icon="Plus" @click="addRlsRow">添加规则</el-button>
        </div>
      </div>
    </el-dialog>

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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import * as echarts from "echarts"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import type { UploadFile } from "element-plus"
import {
  Connection,
  Delete,
  Edit,
  Grid,
  MagicStick,
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
  status?: "confirmed" | "inferred" | "ignored"
  confidence?: number | null
  source?: string | null
  evidence?: string[]
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
const detailVisible = ref(false)
const detailRow = ref<any>(null)
const openDetail = (row: any) => { detailRow.value = row; detailVisible.value = true }
const keyword = ref("")
const typeFilter = ref("")
const statusFilter = ref<number | null>(null)
const quickFilter = ref("all")
const dialogVisible = ref(false)
const dialogActiveTab = ref("connect")
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)
const selectedExcelFile = ref<File | null>(null)
const selectedExcelName = ref("")
const generatingRecommendQuestions = ref(false)

// Schema modal state
const schemaModalVisible = ref(false)
const currentDatasourceId = ref<number | null>(null)
const currentSchema = ref<SchemaMetadata | null>(null)
const drillConfigModalVisible = ref(false)

// RLS
const rlsModalVisible = ref(false)
const rlsLoading = ref(false)
const rlsRules = ref<any[]>([])
const rlsDatasourceId = ref<number | null>(null)
const rlsOperators = ["=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "LIKE"]

const openRlsModal = async (row: DataSourceDetail) => {
  rlsDatasourceId.value = row.id
  rlsModalVisible.value = true
  rlsLoading.value = true
  try {
    const res = await axios.get(`/api/datasources/${row.id}/rls`)
    rlsRules.value = res.data.map((r: any) => ({ ...r, _scopeType: r.user_id ? "user" : "org", _saving: false }))
  } catch { rlsRules.value = [] }
  finally { rlsLoading.value = false }
}

const addRlsRow = () => {
  rlsRules.value.push({
    id: null, table_name: "", column_name: "", operator: "=", filter_value: "",
    org_id: null, user_id: null, is_active: 1, _scopeType: "org", _saving: false,
  })
}

const createRlsRule = async (row: any) => {
  if (!rlsDatasourceId.value) return
  row._saving = true
  try {
    const res = await axios.post(`/api/datasources/${rlsDatasourceId.value}/rls`, {
      table_name: row.table_name, column_name: row.column_name,
      operator: row.operator, filter_value: row.filter_value,
      org_id: row._scopeType === "org" ? row.org_id : null,
      user_id: row._scopeType === "user" ? row.user_id : null,
      is_active: row.is_active,
    })
    Object.assign(row, res.data, { _saving: false })
    ElMessage.success("规则已创建")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建失败")
    row._saving = false
  }
}

const saveRlsRule = async (row: any) => {
  if (!rlsDatasourceId.value || !row.id) return
  row._saving = true
  try {
    await axios.put(`/api/datasources/${rlsDatasourceId.value}/rls/${row.id}`, {
      table_name: row.table_name, column_name: row.column_name,
      operator: row.operator, filter_value: row.filter_value,
      org_id: row._scopeType === "org" ? row.org_id : null,
      user_id: row._scopeType === "user" ? row.user_id : null,
      is_active: row.is_active,
    })
    ElMessage.success("规则已保存")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally { row._saving = false }
}

const deleteRlsRule = async (row: any) => {
  if (row.id && rlsDatasourceId.value) {
    await axios.delete(`/api/datasources/${rlsDatasourceId.value}/rls/${row.id}`)
  }
  const idx = rlsRules.value.indexOf(row)
  if (idx >= 0) rlsRules.value.splice(idx, 1)
}
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
    if (typeFilter.value) {
      const effectiveType = item.source_type === "database" ? "postgresql" : item.source_type
      if (effectiveType !== typeFilter.value) return false
    }
    if (statusFilter.value !== null && statusFilter.value !== undefined && item.is_active !== statusFilter.value) {
      return false
    }
    if (!kw) return true
    return [item.name, item.slug, item.metadata_prompt, item.metrics_prompt]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(kw))
  })
})

const connectorTypes = [
  { value: "postgresql", label: "PostgreSQL", icon: "🐘", defaultPort: "5432" },
  { value: "mysql", label: "MySQL", icon: "🐬", defaultPort: "3306" },
  { value: "clickhouse", label: "ClickHouse", icon: "🖱️", defaultPort: "9000" },
  { value: "mssql", label: "SQL Server", icon: "🪟", defaultPort: "1433" },
  { value: "sqlite", label: "SQLite", icon: "📁", defaultPort: "" },
  { value: "excel", label: "Excel", icon: "📊", defaultPort: "" },
]

const DB_PREFIXES: Record<string, string> = {
  postgresql: "postgresql+psycopg2",
  database: "postgresql+psycopg2",
  mysql: "mysql+pymysql",
  clickhouse: "clickhouse+native",
  mssql: "mssql+pymssql",
  sqlite: "sqlite",
}

const DEFAULT_PORTS: Record<string, string> = {
  postgresql: "5432",
  database: "5432",
  mysql: "3306",
  clickhouse: "9000",
  mssql: "1433",
}

const form = reactive({
  name: "",
  slug: "",
  source_type: "postgresql",
  conn_host: "",
  conn_port: "5432",
  conn_db: "",
  conn_user: "",
  conn_password: "",
  conn_sqlite_path: "",
  conn_advanced: false,
  database_url: "",
  metrics_prompt: "",
})

const isDbConnector = computed(() => form.source_type !== "excel")

const generatedUrl = computed(() => {
  if (form.source_type === "excel") return ""
  if (form.source_type === "sqlite") {
    return form.conn_sqlite_path ? `sqlite:///${form.conn_sqlite_path}` : ""
  }
  if (!form.conn_host || !form.conn_port || !form.conn_db || !form.conn_user) return ""
  const prefix = DB_PREFIXES[form.source_type] || "postgresql+psycopg2"
  const pass = form.conn_password ? `:${encodeURIComponent(form.conn_password)}` : ""
  const suffix = form.source_type === "mysql" ? "?charset=utf8mb4" : ""
  return `${prefix}://${encodeURIComponent(form.conn_user)}${pass}@${form.conn_host}:${form.conn_port}/${form.conn_db}${suffix}`
})

const maskedUrl = computed(() => {
  if (!generatedUrl.value) return ""
  return generatedUrl.value.replace(/:([^@/]+)@/, ":****@")
})

const urlPlaceholder = computed(() => {
  const prefix = DB_PREFIXES[form.source_type] || "postgresql+psycopg2"
  return `${prefix}://user:password@host:port/dbname`
})

const selectConnectorType = (type: string) => {
  form.source_type = type
  const ct = connectorTypes.find(c => c.value === type)
  if (ct?.defaultPort) form.conn_port = ct.defaultPort
  form.conn_advanced = false
}

const recommendQuestionsText = ref("")

const generateRecommendQuestions = async () => {
  if (!isEdit.value || !editId.value) {
    ElMessage.warning("请先保存数据源后再生成推荐问题")
    return
  }

  generatingRecommendQuestions.value = true
  try {
    const response = await axios.post(`/api/datasources/${editId.value}/generate-recommend-questions`)
    const generated = Array.isArray(response.data?.recommend_questions)
      ? response.data.recommend_questions.map((item: unknown) => String(item || "").trim()).filter(Boolean)
      : []
    if (!generated.length) {
      ElMessage.warning("暂未生成可用推荐问题")
      return
    }
    const existing = recommendQuestionsText.value
      .split("\n")
      .map(s => s.trim())
      .filter(Boolean)
    const merged = [...existing]
    const seen = new Set(existing.map(item => item.replace(/\s+/g, "").toLowerCase()))
    generated.forEach(question => {
      const key = question.replace(/\s+/g, "").toLowerCase()
      if (!seen.has(key)) {
        seen.add(key)
        merged.push(question)
      }
    })
    recommendQuestionsText.value = merged.join("\n")
    ElMessage.success("已生成推荐问题，请确认后保存")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成推荐问题失败")
  } finally {
    generatingRecommendQuestions.value = false
  }
}

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

const sourceTypeLabel = (value: string) => {
  const ct = connectorTypes.find(c => c.value === value)
  if (ct) return ct.label
  if (value === "database") return "PostgreSQL"
  return value
}

const schemaTablesCount = (row: DataSourceDetail) => row.schema_metadata?.tables?.length || 0

const schemaFieldsCount = (row: DataSourceDetail) =>
  (row.schema_metadata?.tables || []).reduce((sum, table) => sum + (table.columns?.length || 0), 0)

const recommendationCount = (row: DataSourceDetail) =>
  Array.isArray(row.recommend_questions) ? row.recommend_questions.length : 0

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  dialogActiveTab.value = "connect"
  form.name = ""
  form.slug = ""
  form.source_type = "postgresql"
  form.conn_host = ""
  form.conn_port = "5432"
  form.conn_db = ""
  form.conn_user = ""
  form.conn_password = ""
  form.conn_sqlite_path = ""
  form.conn_advanced = false
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
  dialogActiveTab.value = "connect"
  form.name = row.name
  form.slug = row.slug
  const storedType = row.source_type || "database"
  form.source_type = storedType === "database" ? "postgresql" : storedType
  form.conn_host = ""
  form.conn_port = DEFAULT_PORTS[form.source_type] || "5432"
  form.conn_db = ""
  form.conn_user = ""
  form.conn_password = ""
  form.conn_sqlite_path = ""
  form.conn_advanced = false
  form.database_url = ""
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
  if (!form.name || !form.slug) {
    ElMessage.warning("请填写名称和标识")
    return
  }

  // Build the final database_url
  let finalDatabaseUrl = ""
  if (form.source_type === "excel") {
    // handled separately via upload
  } else if (form.conn_advanced && form.database_url) {
    finalDatabaseUrl = form.database_url
  } else if (form.source_type === "sqlite") {
    if (!form.conn_sqlite_path) { ElMessage.warning("请填写 SQLite 文件路径"); return }
    finalDatabaseUrl = `sqlite:///${form.conn_sqlite_path}`
  } else {
    if (!form.conn_host || !form.conn_port || !form.conn_db || !form.conn_user) {
      ElMessage.warning("请填写主机、端口、数据库名和用户名")
      return
    }
    finalDatabaseUrl = generatedUrl.value
  }

  if (form.source_type !== "excel" && !finalDatabaseUrl && !isEdit.value) {
    ElMessage.warning("请填写连接信息")
    return
  }
  if (form.source_type === "excel" && !isEdit.value && !selectedExcelFile.value) {
    ElMessage.warning("请选择 Excel 文件")
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

    if (form.source_type === "excel" && selectedExcelFile.value) {
      const uploadPayload = new FormData()
      uploadPayload.append("file", selectedExcelFile.value)
      const uploadResponse = await axios.post("/api/datasources/upload-excel", uploadPayload, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      payload.database_url = uploadResponse.data.database_url
    } else if (finalDatabaseUrl) {
      payload.database_url = finalDatabaseUrl
    }

    if (isEdit.value && editId.value) {
      await axios.put(`/api/datasources/${editId.value}`, payload)
      ElMessage.success("数据源已更新")
    } else {
      // The backend auto-detects schema and generates metadata_prompt during creation.
      payload.metadata_prompt = ""
      const response = await axios.post("/api/datasources", payload)
      const generatedQuestionCount = Array.isArray(response.data?.recommend_questions)
        ? response.data.recommend_questions.length
        : 0
      ElMessage.success(
        generatedQuestionCount > 0
          ? `数据源已创建，已自动检测表结构并生成 ${generatedQuestionCount} 个推荐问题`
          : "数据源已创建，已自动检测表结构"
      )
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

const donutRef = ref<HTMLElement | null>(null)
let donutChart: echarts.ECharts | null = null

const legendItems = computed(() => [
  { label: "全部数据源",   value: datasourceStats.value.total,       color: "#3b82f6" },
  { label: "已启用",       value: datasourceStats.value.active,      color: "#16a34a" },
  { label: "已配置表结构", value: datasourceStats.value.schemaReady, color: "#d97706" },
  { label: "Excel 数据源", value: datasourceStats.value.excel,       color: "#8b5cf6" },
])

const updateDonut = () => {
  if (!donutRef.value) return
  if (!donutChart) donutChart = echarts.init(donutRef.value)
  const s = datasourceStats.value
  const inactive = Math.max(0, s.total - s.active)
  const data = [
    { value: s.active,      name: "已启用",       itemStyle: { color: "#16a34a" } },
    { value: s.schemaReady, name: "已配置表结构", itemStyle: { color: "#d97706" } },
    { value: s.excel,       name: "Excel 数据源", itemStyle: { color: "#8b5cf6" } },
    { value: inactive,      name: "已停用",       itemStyle: { color: "#94a3b8" } },
  ].filter(d => d.value > 0)
  if (!data.length) data.push({ value: 1, name: "暂无数据", itemStyle: { color: "#e2e8f0" } })
  donutChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{ type: "pie", radius: ["52%", "80%"], center: ["50%", "50%"], avoidLabelOverlap: false,
      label: { show: true, position: "center",
        formatter: () => `{total|${s.total}}\n{label|数据源总数}`,
        rich: { total: { fontSize: 22, fontWeight: 700, color: "#1e293b", lineHeight: 28 }, label: { fontSize: 11, color: "#94a3b8", lineHeight: 18 } } },
      emphasis: { label: { show: true } }, labelLine: { show: false }, data }],
  }, true)
}

watch(datasourceStats, () => nextTick(updateDonut), { deep: true })
onBeforeUnmount(() => { donutChart?.dispose(); donutChart = null })

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    await authStore.fetchProfile()
  }
  await fetchAll()
  nextTick(updateDonut)
})
</script>

<style scoped>
.detail-modal-header { display: flex; align-items: center; gap: 12px; width: 100%; }
.detail-modal-icon { width: 40px; height: 40px; border-radius: 8px; background: var(--el-color-primary-light-8); color: var(--el-color-primary); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.ds-icon--excel { background: #d1fae5; color: #065f46; }
.ds-icon--mysql, .ds-icon--postgresql { background: #dbeafe; color: #1e40af; }
.detail-modal-title { font-size: 15px; font-weight: 600; }
.detail-modal-sub { font-size: 12px; color: var(--app-text-muted); }
.detail-text-clamp { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; font-size: 12px; line-height: 1.6; }

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

.semantic-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.connector-type-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.connector-type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
  border: 1.5px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  font-size: 12px;
  color: var(--app-text-muted);
  min-width: 76px;
}

.connector-type-card:hover {
  border-color: var(--app-primary);
  color: var(--app-primary);
}

.connector-type-card.is-active {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.06);
  color: var(--app-primary);
  font-weight: 600;
}

.connector-icon {
  font-size: 20px;
  line-height: 1;
}

.connector-label {
  font-size: 11px;
  white-space: nowrap;
}

.connector-url-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: var(--app-surface-muted);
  border-radius: var(--app-radius-sm);
  border: 1px solid var(--app-border-light);
  margin-top: 4px;
}

.url-preview-label {
  font-size: 11px;
  color: var(--app-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.url-preview-value {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  color: var(--app-text);
  word-break: break-all;
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

.rls-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rls-intro {
  padding: 10px 14px;
  background: rgba(99, 102, 241, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: var(--app-radius-sm);
  font-size: 13px;
  color: var(--app-text);
}

.rls-toolbar {
  display: flex;
  justify-content: flex-end;
}

.rls-scope {
  display: flex;
  gap: 6px;
  align-items: center;
}
</style>
