<template>
  <div class="operations-page">
    <header class="ops-header">
      <div>
        <div class="eyebrow">系统管理</div>
        <h2>运营后台</h2>
        <p>查看当前范围内的资源使用、问数负载和资产运行健康状态。</p>
      </div>
      <div class="header-actions">
        <el-tag effect="plain">{{ summary.scope.label }}</el-tag>
        <span class="updated-at">{{ lastUpdatedLabel }}</span>
        <el-tooltip content="刷新运营数据" placement="bottom">
          <el-button
            :icon="Refresh"
            :loading="loading"
            circle
            aria-label="刷新运营数据"
            @click="fetchSummary"
          />
        </el-tooltip>
      </div>
    </header>

    <section class="kpi-grid">
      <div v-for="item in overviewCards" :key="item.key" class="kpi-card">
        <div class="kpi-icon" :class="`tone-${item.tone}`">
          <el-icon><component :is="item.icon" /></el-icon>
        </div>
        <div class="kpi-content">
          <span>{{ item.label }}</span>
          <strong>{{ formatNumber(item.value) }}</strong>
          <small>{{ item.hint }}</small>
        </div>
      </div>
    </section>

    <section class="ops-layout">
      <div class="resource-panel">
        <div class="section-heading">
          <div>
            <h3>资源使用</h3>
            <p>展示已使用的平台资源数量；当前版本不做商业配额限制。</p>
          </div>
          <el-tag size="small" type="success" effect="plain">不限额</el-tag>
        </div>
        <div class="usage-grid">
          <article v-for="item in summary.resource_usage" :key="item.key" class="usage-card">
            <div class="usage-topline">
              <div class="usage-icon">
                <el-icon><component :is="usageIcon(item.key)" /></el-icon>
              </div>
              <div>
                <h4>{{ item.label }}</h4>
                <span>{{ item.description }}</span>
              </div>
            </div>
            <div class="usage-value">
              <strong>{{ formatNumber(item.used) }}</strong>
              <span>{{ item.unit }}</span>
              <em>{{ item.capacity_label }}</em>
            </div>
            <el-progress :percentage="item.share_percent" :stroke-width="8" :show-text="false" />
          </article>
        </div>
      </div>

      <aside class="health-panel">
        <div class="section-heading compact">
          <div>
            <h3>运行健康</h3>
            <p>优先处理影响可用性和可信度的风险。</p>
          </div>
        </div>
        <div class="health-list">
          <div v-for="row in healthRows" :key="row.key" class="health-row">
            <div class="health-main">
              <el-icon :class="row.status"><component :is="row.icon" /></el-icon>
              <div>
                <strong>{{ row.label }}</strong>
                <span>{{ row.suggestion }}</span>
              </div>
            </div>
            <el-tag :type="row.tagType" effect="plain">{{ row.value }}</el-tag>
          </div>
        </div>

        <div class="system-resources">
          <div class="section-heading compact">
            <div>
              <h3>系统资源</h3>
              <p>当前运行主机的基础资源使用情况。</p>
            </div>
          </div>
          <div class="system-resource-list">
            <div v-for="item in systemResourceRows" :key="item.key" class="system-resource-row">
              <div class="resource-line">
                <div>
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.detail }}</span>
                </div>
                <b>{{ item.used_percent }}%</b>
              </div>
              <el-progress :percentage="item.used_percent" :stroke-width="8" :show-text="false" />
              <small>{{ item.footnote }}</small>
            </div>
          </div>
        </div>
      </aside>
    </section>

    <section class="lower-grid">
      <div class="trend-panel">
        <div class="section-heading compact">
          <div>
            <h3>近 7 日问数趋势</h3>
            <p>用于判断业务使用热度和峰值压力。</p>
          </div>
        </div>
        <div class="trend-bars" aria-label="近 7 日问数趋势">
          <div v-for="item in summary.query_trend" :key="item.date" class="trend-item">
            <div class="bar-track">
              <div class="bar-fill" :style="{ height: `${trendHeight(item.count)}%` }" />
            </div>
            <strong>{{ item.count }}</strong>
            <span>{{ formatDay(item.date) }}</span>
          </div>
        </div>
      </div>

      <div class="source-panel">
        <div class="section-heading compact">
          <div>
            <h3>数据源负载排行</h3>
            <p>按历史问数次数排序，帮助识别重点治理对象。</p>
          </div>
        </div>
        <el-empty
          v-if="summary.datasource_usage.length === 0"
          description="暂无数据源负载"
          :image-size="72"
        />
        <div v-else class="source-list">
          <div v-for="item in summary.datasource_usage" :key="item.id" class="source-row">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ formatNumber(item.query_count) }} 次问数</span>
            </div>
            <el-progress :percentage="item.share_percent" :stroke-width="8" />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, type Component } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import {
  Coin,
  Collection,
  DataAnalysis,
  DataLine,
  FolderOpened,
  Grid,
  Monitor,
  Refresh,
  Select,
  TrendCharts,
  User,
  Warning,
} from "@element-plus/icons-vue"

interface ScopeInfo {
  type: "platform" | "organization"
  org_id: number | null
  label: string
}

interface ResourceUsageItem {
  key: string
  label: string
  used: number
  unit: string
  capacity_label: string
  share_percent: number
  status: string
  description: string
}

interface WorkloadInfo {
  queries_total: number
  queries_7d: number
  audit_errors_total: number
  audit_errors_7d: number
  avg_queries_per_user_7d: number
}

interface AssetHealthInfo {
  published_assets: number
  draft_assets: number
  published_asset_ratio: number
  published_datasets: number
  draft_datasets: number
  published_dashboards: number
  inactive_datasources: number
  dataset_refresh_failures_7d: number
  materialized_datasets: number
}

interface RowUsageInfo {
  dataset_rows: number
  materialized_datasets: number
}

interface SystemResourceItem {
  label: string
  used: number
  total: number
  used_percent: number
  unit: string
  detail: string
}

interface SystemResources {
  cpu_load: SystemResourceItem
  memory: SystemResourceItem
  disk: SystemResourceItem
}

interface TrendPoint {
  date: string
  count: number
}

interface DatasourceUsageItem {
  id: number
  name: string
  query_count: number
  share_percent: number
}

interface OperationsSummary {
  scope: ScopeInfo
  generated_at: string | null
  active_users: number
  query_count: number
  asset_count: number
  datasource_count: number
  dashboard_count: number
  dataset_count: number
  big_screen_count: number
  metric_count: number
  organization_count: number
  audit_error_count: number
  resource_usage: ResourceUsageItem[]
  workload: WorkloadInfo
  asset_health: AssetHealthInfo
  row_usage: RowUsageInfo
  system_resources: SystemResources
  query_trend: TrendPoint[]
  datasource_usage: DatasourceUsageItem[]
}

type Tone = "teal" | "blue" | "green" | "amber" | "red"

const emptySummary = (): OperationsSummary => ({
  scope: { type: "organization", org_id: null, label: "当前企业" },
  generated_at: null,
  active_users: 0,
  query_count: 0,
  asset_count: 0,
  datasource_count: 0,
  dashboard_count: 0,
  dataset_count: 0,
  big_screen_count: 0,
  metric_count: 0,
  organization_count: 0,
  audit_error_count: 0,
  resource_usage: [],
  workload: {
    queries_total: 0,
    queries_7d: 0,
    audit_errors_total: 0,
    audit_errors_7d: 0,
    avg_queries_per_user_7d: 0,
  },
  asset_health: {
    published_assets: 0,
    draft_assets: 0,
    published_asset_ratio: 0,
    published_datasets: 0,
    draft_datasets: 0,
    published_dashboards: 0,
    inactive_datasources: 0,
    dataset_refresh_failures_7d: 0,
    materialized_datasets: 0,
  },
  row_usage: {
    dataset_rows: 0,
    materialized_datasets: 0,
  },
  system_resources: {
    cpu_load: {
      label: "CPU 负载",
      used: 0,
      total: 0,
      used_percent: 0,
      unit: "load",
      detail: "尚未加载",
    },
    memory: {
      label: "内存",
      used: 0,
      total: 0,
      used_percent: 0,
      unit: "bytes",
      detail: "尚未加载",
    },
    disk: {
      label: "磁盘",
      used: 0,
      total: 0,
      used_percent: 0,
      unit: "bytes",
      detail: "尚未加载",
    },
  },
  query_trend: [],
  datasource_usage: [],
})

const loading = ref(false)
const summary = ref<OperationsSummary>(emptySummary())

const iconByUsage: Record<string, Component> = {
  users: User,
  datasources: Coin,
  datasets: Collection,
  dashboards: Grid,
  big_screens: Monitor,
  metrics: TrendCharts,
  catalog_assets: FolderOpened,
}

const usageIcon = (key: string) => iconByUsage[key] || DataLine

const formatNumber = (value: number) => Number(value || 0).toLocaleString("zh-CN")

const formatDay = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })
}

const lastUpdatedLabel = computed(() => {
  if (!summary.value.generated_at) return "尚未加载"
  const date = new Date(summary.value.generated_at)
  if (Number.isNaN(date.getTime())) return summary.value.generated_at
  return `更新于 ${date.toLocaleString("zh-CN", { hour12: false })}`
})

const overviewCards = computed<Array<{ key: string; label: string; value: number; hint: string; icon: Component; tone: Tone }>>(() => [
  {
    key: "queries7d",
    label: "7 日问数",
    value: summary.value.workload.queries_7d,
    hint: `累计 ${formatNumber(summary.value.workload.queries_total)} 次`,
    icon: DataAnalysis,
    tone: "teal",
  },
  {
    key: "users",
    label: "账号规模",
    value: summary.value.active_users,
    hint: summary.value.scope.type === "platform" ? `${formatNumber(summary.value.organization_count)} 个企业` : "当前企业用户",
    icon: User,
    tone: "blue",
  },
  {
    key: "publishedAssets",
    label: "已发布资产",
    value: summary.value.asset_health.published_assets,
    hint: `发布率 ${summary.value.asset_health.published_asset_ratio}%`,
    icon: Select,
    tone: "green",
  },
  {
    key: "rows",
    label: "数据集行数",
    value: summary.value.row_usage.dataset_rows,
    hint: `${formatNumber(summary.value.row_usage.materialized_datasets)} 个已物化`,
    icon: Collection,
    tone: "amber",
  },
])

const healthRows = computed(() => [
  {
    key: "audit",
    label: "审计错误",
    value: `${summary.value.workload.audit_errors_7d} 条`,
    suggestion: summary.value.workload.audit_errors_7d > 0 ? "查看审计日志中的失败动作" : "近 7 日无错误审计",
    status: summary.value.workload.audit_errors_7d > 0 ? "danger" : "success",
    tagType: summary.value.workload.audit_errors_7d > 0 ? "danger" : "success",
    icon: summary.value.workload.audit_errors_7d > 0 ? Warning : Select,
  },
  {
    key: "refresh",
    label: "刷新失败",
    value: `${summary.value.asset_health.dataset_refresh_failures_7d} 次`,
    suggestion: summary.value.asset_health.dataset_refresh_failures_7d > 0 ? "优先处理失败数据集刷新" : "近 7 日刷新正常",
    status: summary.value.asset_health.dataset_refresh_failures_7d > 0 ? "danger" : "success",
    tagType: summary.value.asset_health.dataset_refresh_failures_7d > 0 ? "danger" : "success",
    icon: summary.value.asset_health.dataset_refresh_failures_7d > 0 ? Warning : Select,
  },
  {
    key: "datasource",
    label: "停用数据源",
    value: `${summary.value.asset_health.inactive_datasources} 个`,
    suggestion: summary.value.asset_health.inactive_datasources > 0 ? "确认是否影响数据集和问数" : "数据源均处于启用状态",
    status: summary.value.asset_health.inactive_datasources > 0 ? "warning" : "success",
    tagType: summary.value.asset_health.inactive_datasources > 0 ? "warning" : "success",
    icon: summary.value.asset_health.inactive_datasources > 0 ? Warning : Select,
  },
  {
    key: "draft",
    label: "草稿数据集",
    value: `${summary.value.asset_health.draft_datasets} 个`,
    suggestion: summary.value.asset_health.draft_datasets > 0 ? "可推动发布或清理无效草稿" : "暂无待发布数据集",
    status: "normal",
    tagType: "info",
    icon: Collection,
  },
])

const formatBytes = (value: number) => {
  const bytes = Number(value || 0)
  if (bytes <= 0) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB"]
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const scaled = bytes / 1024 ** index
  return `${scaled >= 10 ? scaled.toFixed(0) : scaled.toFixed(1)} ${units[index]}`
}

const systemResourceRows = computed(() => {
  const resources = summary.value.system_resources
  return [
    {
      key: "cpu",
      ...resources.cpu_load,
      footnote: `${resources.cpu_load.used} / ${resources.cpu_load.total || 0} load`,
    },
    {
      key: "memory",
      ...resources.memory,
      footnote: `${formatBytes(resources.memory.used)} / ${formatBytes(resources.memory.total)}`,
    },
    {
      key: "disk",
      ...resources.disk,
      footnote: `${formatBytes(resources.disk.used)} / ${formatBytes(resources.disk.total)}`,
    },
  ]
})

const maxTrendCount = computed(() => Math.max(...summary.value.query_trend.map((item) => item.count), 1))
const trendHeight = (count: number) => Math.max(8, Math.round((count / maxTrendCount.value) * 100))

const normalizeSummary = (payload: Partial<OperationsSummary>): OperationsSummary => ({
  ...emptySummary(),
  ...payload,
  scope: { ...emptySummary().scope, ...(payload.scope || {}) },
  workload: { ...emptySummary().workload, ...(payload.workload || {}) },
  asset_health: { ...emptySummary().asset_health, ...(payload.asset_health || {}) },
  row_usage: { ...emptySummary().row_usage, ...(payload.row_usage || {}) },
  system_resources: { ...emptySummary().system_resources, ...(payload.system_resources || {}) },
  resource_usage: payload.resource_usage || [],
  query_trend: payload.query_trend || [],
  datasource_usage: payload.datasource_usage || [],
})

const fetchSummary = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/operations/summary")
    summary.value = normalizeSummary(response.data)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "运营数据加载失败")
  } finally {
    loading.value = false
  }
}

onMounted(fetchSummary)
</script>

<style scoped>
.operations-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ops-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-soft);
}

.eyebrow {
  margin-bottom: 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.ops-header h2,
.section-heading h3,
.usage-card h4 {
  margin: 0;
}

.ops-header h2 {
  font-size: 24px;
  line-height: 1.25;
}

.ops-header p,
.section-heading p,
.usage-topline span,
.source-row span,
.kpi-content small,
.updated-at {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card,
.usage-card,
.resource-panel,
.health-panel,
.trend-panel,
.source-panel {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-soft);
}

.kpi-card {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 112px;
  padding: 16px;
}

.kpi-icon,
.usage-icon {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  flex: 0 0 auto;
  border-radius: var(--app-radius-sm);
}

.kpi-icon {
  width: 44px;
  height: 44px;
  font-size: 21px;
}

.tone-teal { background: #ccfbf1; color: #0f766e; }
.tone-blue { background: #dbeafe; color: #1d4ed8; }
.tone-green { background: #dcfce7; color: #15803d; }
.tone-amber { background: #fef3c7; color: #b45309; }
.tone-red { background: #fee2e2; color: #b91c1c; }

.kpi-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.kpi-content span {
  color: var(--app-text-muted);
  font-size: 13px;
}

.kpi-content strong {
  color: var(--app-text);
  font-size: 26px;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.ops-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 14px;
  align-items: start;
}

.resource-panel,
.health-panel,
.trend-panel,
.source-panel {
  padding: 16px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.section-heading.compact {
  margin-bottom: 12px;
}

.section-heading h3 {
  font-size: 16px;
  line-height: 1.4;
}

.usage-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.usage-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 174px;
  padding: 14px;
}

.usage-topline {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  min-width: 0;
}

.usage-icon {
  width: 36px;
  height: 36px;
  background: var(--app-surface-subtle);
  color: var(--app-primary);
  font-size: 18px;
}

.usage-card h4 {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.35;
}

.usage-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.usage-value strong {
  font-size: 28px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.usage-value span {
  color: var(--app-text-muted);
  font-size: 13px;
}

.usage-value em {
  margin-left: auto;
  color: var(--app-success);
  font-size: 12px;
  font-style: normal;
}

.health-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.system-resources {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-light);
}

.system-resource-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.system-resource-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.resource-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.resource-line strong {
  display: block;
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.4;
}

.resource-line span,
.system-resource-row small {
  display: block;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.resource-line b {
  color: var(--app-text);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.health-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.health-main {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  min-width: 0;
}

.health-main .el-icon {
  margin-top: 2px;
  font-size: 18px;
}

.health-main .success { color: var(--app-success); }
.health-main .warning { color: var(--app-warning); }
.health-main .danger { color: var(--app-danger); }
.health-main .normal { color: var(--app-info); }

.health-main strong,
.source-row strong {
  display: block;
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.4;
}

.health-main span {
  display: block;
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 14px;
}

.trend-bars {
  display: grid;
  grid-template-columns: repeat(7, minmax(42px, 1fr));
  align-items: end;
  gap: 10px;
  min-height: 210px;
  padding-top: 8px;
}

.trend-item {
  display: grid;
  grid-template-rows: 150px auto auto;
  gap: 6px;
  justify-items: center;
  min-width: 0;
}

.bar-track {
  position: relative;
  width: 100%;
  max-width: 48px;
  height: 150px;
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-subtle);
  overflow: hidden;
}

.bar-fill {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  border-radius: var(--app-radius-xs) var(--app-radius-xs) 0 0;
  background: linear-gradient(180deg, #14b8a6 0%, #0f766e 100%);
}

.trend-item strong {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.trend-item span {
  color: var(--app-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-row {
  display: grid;
  grid-template-columns: minmax(140px, 0.8fr) minmax(160px, 1fr);
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

@media (max-width: 1180px) {
  .kpi-grid,
  .usage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-layout,
  .lower-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .ops-header,
  .header-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .kpi-grid,
  .usage-grid {
    grid-template-columns: 1fr;
  }

  .trend-bars {
    gap: 6px;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .trend-item {
    min-width: 48px;
  }

  .source-row {
    grid-template-columns: 1fr;
  }
}
</style>
