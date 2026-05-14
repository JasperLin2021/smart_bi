<template>
  <div class="page data-access-page">
    <section class="access-hero">
      <div>
        <p class="eyebrow">DATA INTEGRATION</p>
        <h2>数据准备中心</h2>
        <p class="hero-copy">
          面向连接器接入、数据开发、同步与物化、任务运维，把分析前的数据准备能力集中管理。
        </p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadOverview">刷新</el-button>
        <el-button v-if="isAdmin" type="primary" :icon="Plus" @click="go('/data-development?tab=datasources')">新增数据源</el-button>
        <el-button v-else type="primary" @click="requestDialogVisible = true">申请访问权限</el-button>
      </div>
    </section>

    <section class="overview-grid">
      <div class="metric-tile">
        <span>数据源</span>
        <strong>{{ overview.datasources.total }}</strong>
        <small>{{ overview.datasources.schema_ready }} 个已配置表结构</small>
      </div>
      <div class="metric-tile">
        <span>数据集开发</span>
        <strong>{{ overview.datasets.total }}</strong>
        <small>{{ overview.datasets.published }} 个已发布</small>
      </div>
      <div class="metric-tile">
        <span>同步任务</span>
        <strong>{{ overview.sync_tasks.total }}</strong>
        <small>{{ overview.sync_tasks.failed }} 个失败记录</small>
      </div>
      <div class="metric-tile">
        <span>OLAP 数据平台</span>
        <strong>{{ overview.olap.enabled ? "已启用" : "未启用" }}</strong>
        <small>{{ overview.olap.healthy ? "连接正常" : overview.olap.message || "未连接" }}</small>
      </div>
    </section>

    <section class="capability-grid">
      <button
        v-for="item in capabilities"
        :key="item.title"
        type="button"
        class="capability-panel"
        @click="go(item.path)"
      >
        <el-icon :size="22"><component :is="item.icon" /></el-icon>
        <span class="capability-body">
          <strong>{{ item.title }}</strong>
          <small>{{ item.description }}</small>
        </span>
      </button>
    </section>

    <section class="access-layout">
      <el-card class="access-card" shadow="never">
        <template #header>
          <div class="card-title-line">
            <span>接入类型分布</span>
            <el-button text type="primary" @click="go('/data-development?tab=datasources')">管理数据源</el-button>
          </div>
        </template>
        <div class="source-type-list">
          <div v-for="item in overview.source_types" :key="item.type" class="source-type-row">
            <span>{{ sourceTypeLabel(item.type) }}</span>
            <div class="source-type-bar">
              <i :style="{ width: sourceTypeWidth(item.count) }"></i>
            </div>
            <strong>{{ item.count }}</strong>
          </div>
          <el-empty v-if="overview.source_types.length === 0" description="暂无接入数据源" />
        </div>
      </el-card>

      <el-card class="access-card" shadow="never">
        <template #header>
          <div class="card-title-line">
            <span>最近任务运维</span>
            <el-button text type="primary" @click="go('/data-pipelines')">查看加工管道</el-button>
          </div>
        </template>
        <el-table :data="overview.recent_refresh_logs" size="small" empty-text="暂无刷新记录">
          <el-table-column prop="dataset_id" label="数据集" width="90" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small" effect="plain">
                {{ row.status === "success" ? "成功" : "失败" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="row_count" label="行数" width="90" />
          <el-table-column prop="message" label="消息" min-width="160" show-overflow-tooltip />
        </el-table>
      </el-card>
    </section>

    <!-- Access Requests Panel (admin) -->
    <section v-if="isAdmin && pendingRequests.length" class="access-request-panel">
      <div class="panel-header">
        <strong>待审批访问申请</strong>
        <el-tag type="warning" size="small">{{ pendingRequests.length }}</el-tag>
      </div>
      <div class="request-list">
        <div v-for="req in pendingRequests" :key="req.id" class="request-item">
          <div class="request-info">
            <span class="request-resource">
              <el-tag size="small" effect="plain">{{ req.resource_type }}</el-tag>
              {{ req.resource_name || req.resource_id }}
            </span>
            <span class="request-reason">{{ req.reason || "（无说明）" }}</span>
          </div>
          <div class="request-actions">
            <el-button size="small" type="success" plain @click="reviewRequest(req.id, 'approved')">批准</el-button>
            <el-button size="small" type="danger" plain @click="reviewRequest(req.id, 'rejected')">拒绝</el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- Request Access Dialog (non-admin) -->
    <el-dialog v-model="requestDialogVisible" title="申请访问" width="440px">
      <el-form label-position="top">
        <el-form-item label="资源类型">
          <el-select v-model="requestForm.resource_type" style="width:100%">
            <el-option label="数据集" value="dataset" />
            <el-option label="数据源" value="datasource" />
          </el-select>
        </el-form-item>
        <el-form-item label="资源名称（可选）">
          <el-input v-model="requestForm.resource_name" placeholder="说明您要访问的资源名称" />
        </el-form-item>
        <el-form-item label="申请说明">
          <el-input v-model="requestForm.reason" type="textarea" :rows="3" placeholder="说明申请原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="requestDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="requestSaving" @click="submitRequest">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Coin, Document, FolderOpened, Monitor, Plus, Refresh, SetUp } from "@element-plus/icons-vue"
import { useAuthStore } from "@/store/auth"

type Overview = {
  datasources: { total: number; active: number; inactive: number; schema_ready: number }
  datasets: { total: number; published: number; draft: number; materialized: number }
  sync_tasks: { total: number; success: number; failed: number; pending: number }
  source_types: Array<{ type: string; count: number }>
  olap: { enabled: boolean; healthy: boolean; engine?: string; message?: string }
  recent_refresh_logs: Array<{ id: number; dataset_id: number; status: string; row_count: number; message: string | null }>
}

const router = useRouter()
const authStore = useAuthStore()
const isAdmin = computed(() => ["super_admin", "org_admin"].includes(authStore.user?.role || ""))
const loading = ref(false)
const pendingRequests = ref<any[]>([])
const requestDialogVisible = ref(false)
const requestSaving = ref(false)
const requestForm = reactive({ resource_type: "dataset", resource_name: "", reason: "" })
const overview = reactive<Overview>({
  datasources: { total: 0, active: 0, inactive: 0, schema_ready: 0 },
  datasets: { total: 0, published: 0, draft: 0, materialized: 0 },
  sync_tasks: { total: 0, success: 0, failed: 0, pending: 0 },
  source_types: [],
  olap: { enabled: false, healthy: false, engine: "Apache Doris", message: "" },
  recent_refresh_logs: [],
})

const capabilities = [
  {
    title: "连接器接入",
    description: "多源异构接入入口，统一管理 ERP、WMS、CRM、SaaS API 等外部业务系统同步。",
    path: "/data-link",
    icon: Coin,
  },
  {
    title: "数据开发",
    description: "通过数据集选择字段、筛选、聚合、语义层和刷新策略。",
    path: "/data-development?tab=datasets",
    icon: Document,
  },
  {
    title: "同步与物化",
    description: "将数据集全量或增量物化到 Doris，支撑高并发分析。",
    path: "/olap-status",
    icon: SetUp,
  },
  {
    title: "任务运维",
    description: "查看数据加工管道、失败原因和接入链路运行状态。",
    path: "/data-pipelines",
    icon: Monitor,
  },
  {
    title: "数据服务与目录",
    description: "把治理后的数据资产沉淀为目录和 API 服务入口。",
    path: "/data-catalog",
    icon: FolderOpened,
  },
]

const loadOverview = async () => {
  loading.value = true
  try {
    const { data } = await axios.get("/api/data-access/overview")
    Object.assign(overview.datasources, data.datasources || {})
    Object.assign(overview.datasets, data.datasets || {})
    Object.assign(overview.sync_tasks, data.sync_tasks || {})
    Object.assign(overview.olap, data.olap || {})
    overview.source_types = data.source_types || []
    overview.recent_refresh_logs = data.recent_refresh_logs || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据准备总览加载失败")
  } finally {
    loading.value = false
  }
}

const go = (path: string) => {
  router.push(path)
}

const sourceTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    mysql: "MySQL",
    postgresql: "PostgreSQL",
    clickhouse: "ClickHouse",
    mssql: "SQL Server",
    sqlite: "SQLite",
    excel: "Excel 文件",
    database: "数据库",
  }
  return labels[type] || type
}

const sourceTypeWidth = (count: number) => {
  const max = Math.max(1, ...overview.source_types.map((item) => item.count))
  return `${Math.max(8, Math.round((count / max) * 100))}%`
}

const loadPendingRequests = async () => {
  if (!isAdmin.value) return
  try {
    const { data } = await axios.get("/api/access-requests", { params: { status: "pending" } })
    pendingRequests.value = data
  } catch {
    // non-critical
  }
}

const reviewRequest = async (id: number, status: string) => {
  try {
    await axios.put(`/api/access-requests/${id}/review`, { status })
    ElMessage.success(status === "approved" ? "已批准" : "已拒绝")
    loadPendingRequests()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "操作失败")
  }
}

const submitRequest = async () => {
  requestSaving.value = true
  try {
    await axios.post("/api/access-requests", { ...requestForm, resource_id: 0 })
    ElMessage.success("申请已提交，等待管理员审批")
    requestDialogVisible.value = false
    Object.assign(requestForm, { resource_type: "dataset", resource_name: "", reason: "" })
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "提交失败")
  } finally {
    requestSaving.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadPendingRequests()
})
</script>

<style scoped>
.data-access-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.access-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.hero-copy {
  margin: 6px 0 0;
  max-width: 720px;
  color: #64748b;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.overview-grid,
.capability-grid {
  display: grid;
  gap: 12px;
}

.overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.capability-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.metric-tile,
.capability-panel,
.access-card {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
}

.metric-tile {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
}

.metric-tile span,
.metric-tile small,
.capability-panel small {
  color: #64748b;
  font-size: 12px;
}

.metric-tile strong {
  color: #0f172a;
  font-size: 24px;
}

.capability-panel {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 112px;
  padding: 16px;
  color: #0f172a;
  cursor: pointer;
  text-align: left;
}

.capability-panel:hover {
  border-color: #0f766e;
  background: #f8fffc;
}

.capability-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  line-height: 1.45;
}

.access-layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(420px, 1.1fr);
  gap: 14px;
}

.card-title-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 700;
}

.source-type-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.source-type-row {
  display: grid;
  grid-template-columns: 110px 1fr 40px;
  align-items: center;
  gap: 10px;
}

.source-type-bar {
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.source-type-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0f766e;
}

@media (max-width: 1100px) {
  .overview-grid,
  .capability-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .access-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .access-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .hero-actions,
  .overview-grid,
  .capability-grid {
    grid-template-columns: 1fr;
  }
}

.access-request-panel { background: var(--app-surface); border: 1px solid var(--el-color-warning-light-5); border-radius: var(--app-radius); padding: 16px 20px; }
.panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.request-list { display: flex; flex-direction: column; gap: 8px; }
.request-item { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 12px; background: var(--app-bg); border-radius: 6px; border: 1px solid var(--app-border); }
.request-info { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
.request-resource { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; }
.request-reason { font-size: 12px; color: var(--app-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.request-actions { display: flex; gap: 6px; flex-shrink: 0; }
</style>
