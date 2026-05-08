<template>
  <div class="dashboard-page">
    <!-- Header bar -->
    <div class="dash-header">
      <div class="dash-header-left">
        <h2 class="dash-title">{{ currentDashboard?.title || '看板' }}</h2>
        <el-tag v-if="currentDashboard?.status === 'published'" size="small" type="success" effect="plain">已发布</el-tag>
        <span v-if="currentDashboard?.description" class="dash-desc">{{ currentDashboard.description }}</span>
      </div>
      <div class="dash-header-right">
        <el-select
          v-model="selectedId"
          placeholder="切换看板"
          size="small"
          style="width: 200px"
          :loading="listLoading"
          @change="onSwitch"
        >
          <el-option
            v-for="d in dashboards"
            :key="d.id"
            :label="d.title"
            :value="d.id"
          />
        </el-select>
        <el-button size="small" :loading="chartLoading" @click="reload">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button size="small" @click="goEdit">
          <el-icon><EditPen /></el-icon>
          编辑
        </el-button>
      </div>
    </div>

    <!-- Cross-filter bar -->
    <div v-if="activeFilters.length > 0" class="crossfilter-bar">
      <span class="cf-label">过滤中：</span>
      <el-tag
        v-for="f in activeFilters"
        :key="f.field"
        closable
        type="warning"
        effect="plain"
        @close="activeFilters = activeFilters.filter(x => x.field !== f.field)"
      >{{ f.field }} = {{ f.value }}</el-tag>
      <el-button text type="danger" size="small" @click="activeFilters = []">清除</el-button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="chartLoading" class="skeleton-grid">
      <el-skeleton v-for="i in 6" :key="i" animated style="height:200px" />
    </div>

    <!-- Empty -->
    <el-empty
      v-else-if="!currentDashboard || components.length === 0"
      :description="currentDashboard ? '该看板暂无图表组件' : '暂无可用看板'"
      :image-size="100"
    >
      <el-button v-if="currentDashboard" type="primary" @click="goEdit">去编辑</el-button>
      <el-button v-else type="primary" @click="$router.push('/dashboard-center')">前往看板中心</el-button>
    </el-empty>

    <!-- Dashboard grid -->
    <div v-else class="dash-grid">
      <div
        v-for="item in components"
        :key="item.id"
        class="dash-cell"
        :style="cellStyle(item)"
      >
        <PinnedChartCard
          :chart="chartFor(item)"
          :active-filters="activeFilters"
          @delete="() => {}"
          @filter="handleFilter"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Refresh, EditPen } from "@element-plus/icons-vue"
import PinnedChartCard from "@/components/PinnedChartCard.vue"

const router = useRouter()

interface DashboardSummary {
  id: number
  title: string
  description?: string | null
  status: string
  layout_json: { components: DashboardComponent[] } | null
}

interface DashboardComponent {
  id: string
  pinned_chart_id: number
  title: string
  description?: string | null
  chart_type?: string
  sort_order?: string
  w?: number
  h?: number
}

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, any>>
}

interface CrossFilter { field: string; value: any }

const dashboards = ref<DashboardSummary[]>([])
const STORAGE_KEY = "dashboard_selected_id"
const selectedId = ref<number | null>(
  Number(localStorage.getItem(STORAGE_KEY)) || null
)
const listLoading = ref(false)
const chartLoading = ref(false)
const pinnedCharts = ref<PinnedChartData[]>([])
const activeFilters = ref<CrossFilter[]>([])

const currentDashboard = computed(() =>
  dashboards.value.find(d => d.id === selectedId.value) ?? null
)

const components = computed(() =>
  currentDashboard.value?.layout_json?.components ?? []
)

const cellStyle = (c: DashboardComponent) => ({
  gridColumn: `span ${Math.min(Math.max(c.w ?? 6, 3), 12)}`,
  minHeight: `${Math.min(Math.max(c.h ?? 3, 2), 6) * 96}px`,
})

const chartFor = (c: DashboardComponent): PinnedChartData => {
  const found = pinnedCharts.value.find(p => p.id === c.pinned_chart_id)
  return {
    id: c.pinned_chart_id,
    title: c.title,
    description: c.description ?? found?.description ?? null,
    chart_type: c.chart_type ?? found?.chart_type ?? "bar",
    sort_order: c.sort_order ?? found?.sort_order ?? "desc",
    columns: found?.columns ?? [],
    rows: found?.rows ?? [],
  }
}

const handleFilter = (f: CrossFilter) => {
  const idx = activeFilters.value.findIndex(x => x.field === f.field)
  if (idx >= 0) {
    if (activeFilters.value[idx].value === f.value) activeFilters.value.splice(idx, 1)
    else activeFilters.value[idx] = f
  } else {
    activeFilters.value.push(f)
  }
}

async function loadDashboards() {
  listLoading.value = true
  try {
    const r = await axios.get("/api/dashboards", { params: { page: 1, page_size: 50 } })
    dashboards.value = r.data.items ?? []
    // Default to first published, or first overall
    const first = dashboards.value.find(d => d.status === "published") ?? dashboards.value[0]
    // Restore persisted selection if still valid, otherwise default to first
    const persisted = selectedId.value
    const valid = persisted && dashboards.value.some(d => d.id === persisted)
    if (!valid) {
      selectedId.value = first?.id ?? null
    }
    if (selectedId.value) localStorage.setItem(STORAGE_KEY, String(selectedId.value))
  } catch {
    ElMessage.error("看板列表加载失败")
  } finally {
    listLoading.value = false
  }
}

async function loadCharts() {
  chartLoading.value = true
  try {
    const r = await axios.get("/api/pinned-charts/with-data")
    pinnedCharts.value = r.data
  } catch {
    ElMessage.error("图表数据加载失败")
  } finally {
    chartLoading.value = false
  }
}

function onSwitch() {
  activeFilters.value = []
  if (selectedId.value) localStorage.setItem(STORAGE_KEY, String(selectedId.value))
}

function reload() {
  loadCharts()
}

function goEdit() {
  router.push("/dashboard-center")
}

onMounted(async () => {
  await loadDashboards()
  await loadCharts()
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.dash-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.dash-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--app-text);
  white-space: nowrap;
}

.dash-desc {
  font-size: 13px;
  color: var(--app-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.dash-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.crossfilter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(217, 119, 6, 0.06);
  border: 1px solid rgba(217, 119, 6, 0.25);
  border-radius: var(--app-radius-sm);
}

.cf-label {
  font-size: 12px;
  color: var(--app-text-muted);
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.dash-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.dash-cell {
  min-width: 0;
}

@media (max-width: 900px) {
  .dash-header {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    padding: 12px;
  }

  .dash-header-left {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .dash-title {
    white-space: normal;
    line-height: 1.35;
  }

  .dash-header-right {
    width: 100%;
    flex-shrink: 1;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .dash-header-right :deep(.el-select) {
    width: min(100%, 260px) !important;
    max-width: 100%;
    flex: 1 1 200px;
  }

  .dash-header-right :deep(.el-button + .el-button) {
    margin-left: 0;
  }

  .dash-header-right :deep(.el-button) {
    min-height: 36px;
  }

  .dash-grid {
    grid-template-columns: 1fr;
  }
  .dash-cell {
    grid-column: 1 / -1 !important;
  }
  .dash-desc { display: none; }
}
</style>
