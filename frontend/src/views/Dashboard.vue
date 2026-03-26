<template>
  <div class="dashboard-page">
    <!-- Welcome Section -->
    <div class="welcome-section">
      <div class="welcome-content">
        <h2 class="welcome-title">
          {{ greeting }}, {{ authStore.profile?.username || '用户' }}
        </h2>
        <p class="welcome-subtitle">
          {{ currentDate }}
        </p>
      </div>
      <div class="quick-stats">
        <div class="stat-item">
          <div class="stat-value">{{ pinnedCharts.length }}</div>
          <div class="stat-label">固定图表</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ datasourceStore.datasources.length }}</div>
          <div class="stat-label">数据源</div>
        </div>
      </div>
    </div>

    <!-- Pinned Charts Section -->
    <div class="charts-section" v-if="pinnedCharts.length > 0">
      <div class="section-header">
        <div class="section-title-group">
          <h3 class="section-title">
            <el-icon><Star /></el-icon>
            我的图表
          </h3>
          <el-tag size="small" effect="plain" round>{{ pinnedCharts.length }} 个</el-tag>
        </div>
        <el-button size="small" @click="refreshCharts" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      
      <el-row :gutter="20">
        <el-col 
          v-for="chart in pinnedCharts" 
          :key="chart.id" 
          :xs="24" 
          :sm="12" 
          :lg="8"
          class="chart-col"
        >
          <PinnedChartCard :chart="chart" @delete="deletePinnedChart" />
        </el-col>
      </el-row>
    </div>

    <!-- Empty State -->
    <div v-else class="empty-section">
      <div class="empty-card">
        <div class="empty-icon">
          <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="20" width="64" height="48" rx="8" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M8 36h64" stroke="currentColor" stroke-width="2"/>
            <rect x="16" y="44" width="20" height="16" rx="4" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M44 52l8-8 12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3 class="empty-title">暂无固定图表</h3>
        <p class="empty-description">
          在「智能问数」中提问并生成图表后，点击固定按钮将图表添加到此处
        </p>
        <el-button type="primary" @click="goToQuery">
          <el-icon><ChatDotRound /></el-icon>
          开始问数
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Star, Refresh, ChatDotRound } from "@element-plus/icons-vue"
import PinnedChartCard from "@/components/PinnedChartCard.vue"
import { useDatasourceStore } from "@/store/datasource"
import { useAuthStore } from "@/store/auth"

const router = useRouter()
const datasourceStore = useDatasourceStore()
const authStore = useAuthStore()

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, any>>
}

const pinnedCharts = ref<PinnedChartData[]>([])
const loading = ref(false)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const currentDate = computed(() => {
  const now = new Date()
  const options: Intl.DateTimeFormatOptions = { 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric',
    weekday: 'long'
  }
  return now.toLocaleDateString('zh-CN', options)
})

const fetchPinnedCharts = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (datasourceStore.currentId) params.datasource_id = datasourceStore.currentId
    const response = await axios.get("/api/pinned-charts/with-data", { params })
    pinnedCharts.value = response.data
  } catch (error) {
    console.error("固定图表加载失败", error)
  } finally {
    loading.value = false
  }
}

const refreshCharts = () => {
  fetchPinnedCharts()
}

const deletePinnedChart = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除这个图表吗？", "提示", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning"
    })
    await axios.delete(`/api/pinned-charts/${id}`)
    ElMessage.success("已删除")
    await fetchPinnedCharts()
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error("删除失败")
    }
  }
}

const goToQuery = () => {
  router.push("/smart-query")
}

watch(() => datasourceStore.currentId, () => {
  fetchPinnedCharts()
})

onMounted(() => {
  fetchPinnedCharts()
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.welcome-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28px 32px;
  background: linear-gradient(135deg, #06b6d4 0%, #0891b2 50%, #0e7490 100%);
  border-radius: var(--app-radius);
  color: white;
  position: relative;
  overflow: hidden;
}

.welcome-section::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -20%;
  width: 60%;
  height: 200%;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  pointer-events: none;
}

.welcome-content {
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
}

.welcome-subtitle {
  font-size: 14px;
  opacity: 0.85;
  margin: 0;
}

.quick-stats {
  display: flex;
  gap: 32px;
  position: relative;
  z-index: 1;
}

.stat-item {
  text-align: center;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  backdrop-filter: blur(10px);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 4px;
}

.charts-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--app-text);
}

.section-title .el-icon {
  color: #f59e0b;
}

.chart-col {
  margin-bottom: 20px;
}

.empty-section {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.empty-card {
  text-align: center;
  padding: 48px;
  background: var(--app-surface);
  border-radius: var(--app-radius);
  border: 2px dashed var(--app-border);
  max-width: 400px;
}

.empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  color: var(--app-text-light);
}

.empty-icon svg {
  width: 100%;
  height: 100%;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--app-text);
}

.empty-description {
  font-size: 14px;
  color: var(--app-text-muted);
  margin: 0 0 24px 0;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .welcome-section {
    flex-direction: column;
    text-align: center;
    gap: 24px;
  }

  .quick-stats {
    width: 100%;
    justify-content: center;
  }
}
</style>
