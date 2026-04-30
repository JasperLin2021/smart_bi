<template>
  <div class="governance-page metric-page">
    <section class="governance-hero">
      <div class="governance-hero-copy">
        <p class="governance-kicker">TRUSTED METRIC CENTER</p>
        <h2 class="governance-title">可信指标中心</h2>
        <p class="governance-desc">统一维护指标口径、认证状态、负责人、质量说明和数据血缘，让问数、看板和数据目录使用同一套可信指标。</p>
      </div>
      <div class="governance-actions">
        <el-button :icon="Refresh" @click="fetchMetrics" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增指标</el-button>
      </div>
    </section>

    <section class="governance-summary-grid">
      <div class="governance-summary-card">
        <span>全部指标</span>
        <strong>{{ metricStats.total }}</strong>
      </div>
      <div class="governance-summary-card trusted">
        <span>已认证</span>
        <strong>{{ metricStats.certified }}</strong>
      </div>
      <div class="governance-summary-card pending">
        <span>待审核</span>
        <strong>{{ metricStats.pending }}</strong>
      </div>
      <div class="governance-summary-card risk">
        <span>质量风险</span>
        <strong>{{ metricStats.risk }}</strong>
      </div>
    </section>

    <el-card class="governance-workbench metric-card" shadow="never">
      <div class="governance-toolbar">
        <div class="governance-filters">
          <el-input
            v-model="keyword"
            class="governance-search"
            clearable
            :prefix-icon="Search"
            placeholder="搜索指标 / 口径 / 负责人"
          />
          <el-select v-model="selectedDatasourceFilter" clearable placeholder="数据源" class="governance-filter">
            <el-option
              v-for="ds in datasourceStore.datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
          <el-select v-model="certificationFilter" clearable placeholder="认证状态" class="governance-filter">
            <el-option label="草稿" value="draft" />
            <el-option label="待审核" value="pending_review" />
            <el-option label="已认证" value="certified" />
            <el-option label="已废弃" value="deprecated" />
          </el-select>
          <el-select v-model="qualityFilter" clearable placeholder="质量状态" class="governance-filter">
            <el-option label="未知" value="unknown" />
            <el-option label="正常" value="normal" />
            <el-option label="过期" value="stale" />
            <el-option label="异常" value="error" />
          </el-select>
        </div>
        <div class="governance-quick-filters">
          <button
            v-for="item in metricQuickFilters"
            :key="item.value"
            type="button"
            class="governance-pill"
            :class="{ 'is-active': quickFilter === item.value }"
            @click="quickFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="governance-muted">共 {{ filteredMetrics.length }} 个结果</span>
      </div>
      <el-table
        class="governance-table"
        :data="filteredMetrics"
        v-loading="loading"
        row-key="id"
        empty-text="暂无指标"
        @row-click="openDialog"
      >
        <template #empty>
          <div class="governance-empty">
            <strong>还没有匹配的可信指标</strong>
            <span>新增指标并补齐口径、公式、负责人和质量说明后，问数、看板与数据目录会复用同一套定义。</span>
            <el-button type="primary" :icon="Plus" @click="openDialog()">新增指标</el-button>
          </div>
        </template>
        <el-table-column label="指标与口径" min-width="260">
          <template #default="{ row }">
            <div class="metric-name-cell">
              <div class="metric-title-row">
                <strong>{{ row.name }}</strong>
                <el-tag v-if="row.unit" size="small" effect="plain">{{ row.unit }}</el-tag>
              </div>
              <span>{{ row.description || row.definition || "未填写口径说明" }}</span>
              <div class="tag-row" v-if="row.tags?.length">
                <el-tag v-for="tag in row.tags" :key="tag" size="small" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="可信状态" width="150">
          <template #default="{ row }">
            <div class="status-stack">
              <el-tag :type="certificationTagType(row.certification_status)" effect="plain">
                {{ certificationLabel(row.certification_status) }}
              </el-tag>
              <small v-if="row.certified_by">认证人：{{ row.certified_by }}</small>
              <div class="governance-progress" :aria-label="`可信完整度 ${trustScore(row)}%`">
                <span :style="{ width: `${trustScore(row)}%` }"></span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="质量" width="140">
          <template #default="{ row }">
            <div class="status-stack">
              <el-tag :type="qualityTagType(row.quality_status)" effect="plain">
                {{ qualityLabel(row.quality_status) }}
              </el-tag>
              <small>{{ row.quality_message || "暂无说明" }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="190">
          <template #default="{ row }">
            <div class="source-cell">
              <strong>{{ getDatasourceName(row.datasource_id) }}</strong>
              <span>{{ [row.table_name, row.column_name].filter(Boolean).join(".") || "未绑定字段" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="公式" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.formula || row.definition }}</template>
        </el-table-column>
        <el-table-column label="版本 / 更新" width="170">
          <template #default="{ row }">
            <div class="version-cell">
              <strong>{{ row.caliber_version || "v1" }}</strong>
              <span>{{ formatDate(row.data_updated_at) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : row.status === 'archived' ? 'info' : 'warning'" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <div class="governance-action-group">
              <el-button text type="primary" @click.stop="openLineage(row)">血缘</el-button>
              <el-button text type="primary" @click.stop="openDialog(row)">编辑</el-button>
              <el-dropdown trigger="click" @click.stop>
                <el-button text :icon="MoreFilled">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :icon="Delete" @click="deleteMetric(row.id)">删除指标</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑可信指标' : '新增可信指标'"
      width="min(1080px, calc(100vw - 32px))"
      class="metric-dialog governance-modal"
      destroy-on-close
    >
      <el-form :model="form" label-position="top">
        <div class="governance-modal-shell">
          <aside class="governance-modal-rail">
            <div>
              <p class="governance-modal-title">可信指标配置</p>
              <p class="governance-modal-copy">先让业务读得懂，再把口径落到字段、公式、负责人和质量说明。</p>
            </div>
            <div class="governance-modal-steps">
              <div
                v-for="(step, index) in metricFormSteps"
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
                <dt>数据源</dt>
                <dd>{{ form.datasource_id ? getDatasourceName(form.datasource_id) : '未选择' }}</dd>
              </div>
              <div>
                <dt>认证</dt>
                <dd>{{ certificationLabel(form.certification_status) }}</dd>
              </div>
              <div>
                <dt>质量</dt>
                <dd>{{ qualityLabel(form.quality_status) }}</dd>
              </div>
            </dl>
            <div class="governance-modal-tip">已认证指标会在数据目录、问数结果和看板配置中优先作为可信口径展示。</div>
          </aside>

          <div class="governance-modal-main">
        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <div>
              <h3>基础信息</h3>
              <p>业务用户理解指标时最先看到的名称、定义和负责人。</p>
            </div>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="数据源" required>
                <el-select v-model="form.datasource_id" filterable placeholder="请选择数据源" style="width: 100%">
                  <el-option
                    v-for="ds in datasourceStore.datasources"
                    :key="ds.id"
                    :label="ds.name"
                    :value="ds.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="指标名称" required>
                <el-input v-model="form.name" maxlength="128" placeholder="如：回款率、月活客户数" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="负责人">
                <el-input v-model="form.owner_name" placeholder="如：财务负责人、销售运营" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="单位">
                <el-input v-model="form.unit" placeholder="如：元、%、单、个" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="一句话描述">
            <el-input v-model="form.description" type="textarea" :rows="2" placeholder="在列表、目录和问数结果中展示的简短解释" />
          </el-form-item>
          <el-form-item label="指标定义" required>
            <el-input v-model="form.definition" type="textarea" :rows="3" placeholder="清楚说明统计对象、时间范围、包含/排除规则和业务口径" />
          </el-form-item>
        </section>

        <section class="governance-dialog-section">
          <div class="governance-section-head">
            <div>
              <h3>计算口径</h3>
              <p>把业务口径落到表、字段和公式，供 Text2SQL、看板和目录复用。</p>
            </div>
            <el-button :loading="generatingFormula" @click="generateFormula">AI 生成公式</el-button>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="8">
              <el-form-item label="表名">
                <el-input v-model="form.table_name" placeholder="如：orders" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="字段名">
                <el-input v-model="form.column_name" placeholder="如：net_amount" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="聚合方式">
                <el-select v-model="form.aggregation" style="width: 100%">
                  <el-option label="求和" value="sum" />
                  <el-option label="平均" value="avg" />
                  <el-option label="计数" value="count" />
                  <el-option label="最大值" value="max" />
                  <el-option label="最小值" value="min" />
                  <el-option label="比率" value="ratio" />
                  <el-option label="自定义" value="custom" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="计算公式">
            <el-input v-model="form.formula" type="textarea" :rows="3" placeholder="如：SUM(received_amount) / SUM(receivable_amount)" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="标签">
                <el-input v-model="form.tags_text" placeholder="多个标签用逗号或换行分隔" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="适用维度">
                <el-input v-model="form.dimensions_text" placeholder="如：region, channel, month" />
              </el-form-item>
            </el-col>
          </el-row>
        </section>

        <section class="governance-dialog-section trust-section">
          <div class="governance-section-head">
            <div>
              <h3>可信治理</h3>
              <p>认证状态、质量状态和更新时间会同步到数据目录，帮助用户判断这个数是否可信。</p>
            </div>
          </div>
          <el-row :gutter="16">
            <el-col :xs="24" :md="8">
              <el-form-item label="认证状态">
                <el-select v-model="form.certification_status" style="width: 100%">
                  <el-option label="草稿" value="draft" />
                  <el-option label="待审核" value="pending_review" />
                  <el-option label="已认证" value="certified" />
                  <el-option label="已废弃" value="deprecated" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="发布状态">
                <el-select v-model="form.status" style="width: 100%">
                  <el-option label="草稿" value="draft" />
                  <el-option label="已发布" value="published" />
                  <el-option label="已归档" value="archived" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="质量状态">
                <el-select v-model="form.quality_status" style="width: 100%">
                  <el-option label="未知" value="unknown" />
                  <el-option label="正常" value="normal" />
                  <el-option label="过期" value="stale" />
                  <el-option label="异常" value="error" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="口径版本">
                <el-input v-model="form.caliber_version" placeholder="如：v2026.04" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="数据更新时间">
                <el-date-picker
                  v-model="form.data_updated_at"
                  type="datetime"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  placeholder="选择最近一次数据更新时间"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="质量说明">
            <el-input v-model="form.quality_message" type="textarea" :rows="2" placeholder="如：与财务月结口径一致；最近一次刷新失败原因" />
          </el-form-item>
          <el-form-item label="血缘信息">
            <el-input
              v-model="form.lineage_text"
              type="textarea"
              :rows="4"
              class="code-input"
              placeholder='可填 JSON，如 {"source_tables":["orders","payments"]}；也可直接用逗号分隔表名'
            />
          </el-form-item>
          <el-form-item label="启用状态">
            <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </section>
          </div>
        </div>
      </el-form>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">建议保存前至少补齐定义、公式、负责人和质量说明，避免业务侧出现多个口径。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="saveMetric" :loading="saving">保存指标</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="lineageVisible"
      title="指标血缘与可信说明"
      width="min(860px, calc(100vw - 32px))"
      class="governance-modal lineage-governance-dialog"
    >
      <div v-loading="lineageLoading" class="lineage-dialog">
        <template v-if="lineage">
          <section class="lineage-hero">
            <div>
              <p class="lineage-kicker">METRIC LINEAGE</p>
              <h3>{{ lineage.metric.name }}</h3>
              <span>查看公式、来源字段、上游表和可信状态，判断这个指标能否直接用于经营决策。</span>
            </div>
          </section>
          <section class="lineage-summary">
            <div>
              <span>指标</span>
              <strong>{{ lineage.metric.name }}</strong>
            </div>
            <div>
              <span>数据源</span>
              <strong>{{ lineage.datasource.name || "-" }}</strong>
            </div>
            <div>
              <span>认证</span>
              <el-tag :type="certificationTagType(lineage.trust.certification_status)" effect="plain">
                {{ certificationLabel(lineage.trust.certification_status) }}
              </el-tag>
            </div>
            <div>
              <span>质量</span>
              <el-tag :type="qualityTagType(lineage.trust.quality_status)" effect="plain">
                {{ qualityLabel(lineage.trust.quality_status) }}
              </el-tag>
            </div>
          </section>

          <dl class="lineage-list">
            <dt>公式</dt>
            <dd>{{ lineage.metric.formula || "-" }}</dd>
            <dt>来源字段</dt>
            <dd>{{ [lineage.source.table_name, lineage.source.column_name].filter(Boolean).join(".") || "-" }}</dd>
            <dt>来源表</dt>
            <dd>{{ lineageSourceTables.join("、") || "-" }}</dd>
            <dt>口径版本</dt>
            <dd>{{ lineage.metric.caliber_version || "v1" }}</dd>
            <dt>数据更新时间</dt>
            <dd>{{ formatDate(lineage.trust.data_updated_at) }}</dd>
            <dt>质量说明</dt>
            <dd>{{ lineage.trust.quality_message || "-" }}</dd>
          </dl>
          <pre class="lineage-json">{{ lineageJsonText }}</pre>
        </template>
      </div>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">血缘信息来自指标配置和数据源元数据，后续会用于解释问数结果。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="lineageVisible = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Delete, MoreFilled, Plus, Refresh, Search } from "@element-plus/icons-vue"
import { useDatasourceStore } from "@/store/datasource"

interface Metric {
  id: number
  datasource_id: number
  name: string
  description: string | null
  definition: string
  table_name: string | null
  column_name: string | null
  formula: string | null
  owner_name: string | null
  unit: string | null
  aggregation: string
  tags: string[] | null
  status: string
  dimensions: string[] | null
  certification_status: string
  certified_by: string | null
  certified_at: string | null
  caliber_version: string
  data_updated_at: string | null
  quality_status: string
  quality_message: string | null
  lineage_json: Record<string, unknown> | null
  is_active: number
}

interface MetricForm {
  datasource_id: number | null
  name: string
  description: string
  definition: string
  table_name: string
  column_name: string
  formula: string
  owner_name: string
  unit: string
  aggregation: string
  tags_text: string
  status: string
  dimensions_text: string
  certification_status: string
  caliber_version: string
  data_updated_at: string | null
  quality_status: string
  quality_message: string
  lineage_text: string
  is_active: number
}

interface MetricLineage {
  metric: {
    id: number
    name: string
    definition: string
    formula: string | null
    unit: string | null
    aggregation: string
    caliber_version: string
  }
  datasource: {
    id: number | null
    name: string | null
    source_type: string | null
  }
  source: {
    table_name: string | null
    column_name: string | null
    lineage: Record<string, unknown> | null
  }
  trust: {
    certification_status: string
    certified_by: string | null
    certified_at: string | null
    quality_status: string
    quality_message: string | null
    data_updated_at: string | null
  }
  usage: {
    catalog_asset: string
    datasource_id: number | null
  }
}

const metrics = ref<Metric[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const generatingFormula = ref(false)
const datasourceStore = useDatasourceStore()
const selectedDatasourceFilter = ref<number | null>(null)
const certificationFilter = ref("")
const qualityFilter = ref("")
const quickFilter = ref("all")
const keyword = ref("")
const lineageVisible = ref(false)
const lineageLoading = ref(false)
const lineage = ref<MetricLineage | null>(null)

const emptyForm = (): MetricForm => ({
  datasource_id: null,
  name: "",
  description: "",
  definition: "",
  table_name: "",
  column_name: "",
  formula: "",
  owner_name: "",
  unit: "",
  aggregation: "sum",
  tags_text: "",
  status: "published",
  dimensions_text: "",
  certification_status: "draft",
  caliber_version: "v1",
  data_updated_at: null,
  quality_status: "unknown",
  quality_message: "",
  lineage_text: "",
  is_active: 1,
})

const form = ref<MetricForm>(emptyForm())

const metricFormSteps = computed(() => [
  {
    label: "基础信息",
    desc: "名称、定义、负责人让业务知道这个指标是什么",
    done: Boolean(form.value.datasource_id && form.value.name.trim() && form.value.definition.trim()),
  },
  {
    label: "计算口径",
    desc: "绑定表字段、聚合方式和计算公式",
    done: Boolean(form.value.table_name.trim() || form.value.column_name.trim() || form.value.formula.trim()),
  },
  {
    label: "可信治理",
    desc: "认证状态、质量说明、血缘和更新时间",
    done: Boolean(
      form.value.certification_status === "certified" ||
      form.value.quality_message.trim() ||
      form.value.lineage_text.trim()
    ),
  },
])

const metricQuickFilters = [
  { label: "全部", value: "all" },
  { label: "已认证", value: "certified" },
  { label: "待审核", value: "pending" },
  { label: "质量风险", value: "risk" },
  { label: "未绑定字段", value: "unbound" },
]

const fetchMetrics = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/metrics")
    metrics.value = response.data.items
  } catch (error) {
    ElMessage.error("加载指标列表失败")
  } finally {
    loading.value = false
  }
}

const metricStats = computed(() => {
  const total = metrics.value.length
  const certified = metrics.value.filter(item => item.certification_status === "certified").length
  const pending = metrics.value.filter(item => item.certification_status === "pending_review").length
  const risk = metrics.value.filter(item => ["stale", "error"].includes(item.quality_status)).length
  return { total, certified, pending, risk }
})

const filteredMetrics = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  return metrics.value.filter(item => {
    if (quickFilter.value === "certified" && item.certification_status !== "certified") return false
    if (quickFilter.value === "pending" && item.certification_status !== "pending_review") return false
    if (quickFilter.value === "risk" && !["stale", "error"].includes(item.quality_status)) return false
    if (quickFilter.value === "unbound" && (item.table_name || item.column_name)) return false
    if (selectedDatasourceFilter.value && item.datasource_id !== selectedDatasourceFilter.value) {
      return false
    }
    if (certificationFilter.value && item.certification_status !== certificationFilter.value) {
      return false
    }
    if (qualityFilter.value && item.quality_status !== qualityFilter.value) {
      return false
    }
    if (!normalizedKeyword) {
      return true
    }
    return [item.name, item.description, item.definition, item.owner_name, item.formula]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(normalizedKeyword))
  })
})

const lineageSourceTables = computed(() => {
  const sourceTables = lineage.value?.source.lineage?.source_tables
  return Array.isArray(sourceTables) ? sourceTables.map(item => String(item)) : []
})

const lineageJsonText = computed(() => {
  if (!lineage.value?.source.lineage) {
    return "{}"
  }
  return JSON.stringify(lineage.value.source.lineage, null, 2)
})

const getDatasourceName = (datasourceId: number) => {
  return datasourceStore.datasources.find(ds => ds.id === datasourceId)?.name || `数据源 #${datasourceId}`
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
  }
  return labels[status] || status
}

const certificationLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审核",
    certified: "已认证",
    deprecated: "已废弃",
  }
  return labels[status] || status
}

const certificationTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    draft: "info",
    pending_review: "warning",
    certified: "success",
    deprecated: "danger",
  }
  return types[status] || "info"
}

const qualityLabel = (status: string) => {
  const labels: Record<string, string> = {
    unknown: "未知",
    normal: "正常",
    stale: "过期",
    error: "异常",
  }
  return labels[status] || status
}

const qualityTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    unknown: "info",
    normal: "success",
    stale: "warning",
    error: "danger",
  }
  return types[status] || "info"
}

const formatDate = (value?: string | null) => {
  if (!value) {
    return "未记录"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString("zh-CN", { hour12: false })
}

const trustScore = (metric: Metric) => {
  let score = 20
  if (metric.definition) score += 15
  if (metric.formula) score += 20
  if (metric.owner_name) score += 10
  if (metric.certification_status === "certified") score += 20
  if (metric.quality_status === "normal") score += 10
  if (metric.lineage_json) score += 5
  return Math.min(score, 100)
}

const parseList = (value: string) => {
  const items = value
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean)
  return items.length > 0 ? items : null
}

const parseLineage = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  try {
    return JSON.parse(trimmed)
  } catch (error) {
    const sourceTables = parseList(trimmed) || []
    return { source_tables: sourceTables }
  }
}

const formatLineage = (value: Record<string, unknown> | null) => {
  if (!value) {
    return ""
  }
  return JSON.stringify(value, null, 2)
}

const buildPayload = () => ({
  datasource_id: form.value.datasource_id,
  name: form.value.name,
  description: form.value.description || null,
  definition: form.value.definition,
  table_name: form.value.table_name || null,
  column_name: form.value.column_name || null,
  formula: form.value.formula || null,
  owner_name: form.value.owner_name || null,
  unit: form.value.unit || null,
  aggregation: form.value.aggregation || "sum",
  tags: parseList(form.value.tags_text),
  status: form.value.status || "published",
  dimensions: parseList(form.value.dimensions_text),
  certification_status: form.value.certification_status || "draft",
  caliber_version: form.value.caliber_version || "v1",
  data_updated_at: form.value.data_updated_at || null,
  quality_status: form.value.quality_status || "unknown",
  quality_message: form.value.quality_message || null,
  lineage_json: parseLineage(form.value.lineage_text),
  is_active: form.value.is_active,
})

const openDialog = (metric?: Metric) => {
  if (metric) {
    editingId.value = metric.id
    form.value = {
      datasource_id: metric.datasource_id,
      name: metric.name || "",
      description: metric.description || "",
      definition: metric.definition || "",
      table_name: metric.table_name || "",
      column_name: metric.column_name || "",
      formula: metric.formula || "",
      owner_name: metric.owner_name || "",
      unit: metric.unit || "",
      aggregation: metric.aggregation || "sum",
      tags_text: (metric.tags || []).join(", "),
      status: metric.status || "published",
      dimensions_text: (metric.dimensions || []).join(", "),
      certification_status: metric.certification_status || "draft",
      caliber_version: metric.caliber_version || "v1",
      data_updated_at: metric.data_updated_at || null,
      quality_status: metric.quality_status || "unknown",
      quality_message: metric.quality_message || "",
      lineage_text: formatLineage(metric.lineage_json),
      is_active: metric.is_active ?? 1,
    }
  } else {
    editingId.value = null
    form.value = emptyForm()
  }
  dialogVisible.value = true
}

const saveMetric = async () => {
  if (!form.value.datasource_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请填写数据源、指标名称和指标定义")
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await axios.put(`/api/metrics/${editingId.value}`, payload)
    } else {
      await axios.post("/api/metrics", payload)
    }
    ElMessage.success("保存成功")
    dialogVisible.value = false
    fetchMetrics()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const generateFormula = async () => {
  if (!form.value.datasource_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请先选择数据源并填写指标名称、定义")
    return
  }
  generatingFormula.value = true
  try {
    const response = await axios.post("/api/metrics/generate-formula", buildPayload())
    form.value.formula = response.data.formula || ""
    ElMessage.success("已生成计算公式")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成公式失败")
  } finally {
    generatingFormula.value = false
  }
}

const openLineage = async (metric: Metric) => {
  lineageVisible.value = true
  lineageLoading.value = true
  lineage.value = null
  try {
    const response = await axios.get(`/api/metrics/${metric.id}/lineage`)
    lineage.value = response.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "加载指标血缘失败")
  } finally {
    lineageLoading.value = false
  }
}

const deleteMetric = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定删除该指标？删除后数据目录中的指标资产也会同步移除。", "提示", { type: "warning" })
    await axios.delete(`/api/metrics/${id}`)
    ElMessage.success("删除成功")
    fetchMetrics()
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error("删除失败")
    }
  }
}

onMounted(() => {
  datasourceStore.fetchDatasources()
  fetchMetrics()
})
</script>

<style scoped>
.metric-page {
  padding: 0;
}

.governance-summary-card.trusted {
  border-top: 3px solid #16a34a;
}

.governance-summary-card.pending {
  border-top: 3px solid #d97706;
}

.governance-summary-card.risk {
  border-top: 3px solid #dc2626;
}

.metric-card {
  border-radius: var(--app-radius);
}

.metric-card :deep(.el-table .cell) {
  line-height: 1.5;
}

.metric-name-cell,
.source-cell,
.version-cell,
.status-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.metric-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.metric-title-row strong,
.source-cell strong,
.version-cell strong {
  color: var(--app-text);
}

.metric-name-cell span,
.source-cell span,
.version-cell span,
.status-stack small {
  color: var(--app-text-muted);
  line-height: 1.45;
}

.tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.governance-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.code-input :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.lineage-dialog {
  min-height: 180px;
  padding: 20px;
}

.lineage-hero {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.lineage-kicker {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.lineage-hero h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
}

.lineage-hero span {
  display: block;
  margin-top: 6px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.lineage-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.lineage-summary div {
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.lineage-summary span {
  display: block;
  margin-bottom: 8px;
  color: var(--app-text-muted);
  font-size: 13px;
}

.lineage-summary strong {
  color: var(--app-text);
}

.lineage-list {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 12px 16px;
  margin: 0 0 16px;
}

.lineage-list dt {
  color: var(--app-text-muted);
}

.lineage-list dd {
  margin: 0;
  color: var(--app-text);
  word-break: break-word;
}

.lineage-json {
  max-height: 220px;
  overflow: auto;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .lineage-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .lineage-summary {
    grid-template-columns: 1fr;
  }

  .lineage-list {
    grid-template-columns: 1fr;
  }
}
</style>
