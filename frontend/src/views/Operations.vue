<template>
  <div class="operations-page">
    <div class="toolbar">
      <h2>运营后台</h2>
      <el-button :loading="loading" @click="fetchSummary">刷新</el-button>
    </div>

    <section class="metrics-grid">
      <div v-for="item in metricCards" :key="item.key" class="metric-tile">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <section class="ops-section">
      <h3>运行关注</h3>
      <el-table :data="riskRows" border>
        <el-table-column prop="name" label="项目" />
        <el-table-column prop="value" label="当前值" width="140" />
        <el-table-column prop="suggestion" label="处理建议" />
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"

interface OperationsSummary {
  active_users: number
  query_count: number
  asset_count: number
  dashboard_count: number
  dataset_count: number
  big_screen_count: number
  audit_error_count: number
}

const loading = ref(false)
const summary = ref<OperationsSummary>({
  active_users: 0,
  query_count: 0,
  asset_count: 0,
  dashboard_count: 0,
  dataset_count: 0,
  big_screen_count: 0,
  audit_error_count: 0,
})

const metricCards = computed(() => [
  { key: "users", label: "活跃用户", value: summary.value.active_users },
  { key: "queries", label: "问数次数", value: summary.value.query_count },
  { key: "assets", label: "资产数量", value: summary.value.asset_count },
  { key: "dashboards", label: "看板数量", value: summary.value.dashboard_count },
  { key: "datasets", label: "数据集数量", value: summary.value.dataset_count },
  { key: "bigScreens", label: "大屏数量", value: summary.value.big_screen_count },
])

const riskRows = computed(() => [
  {
    name: "错误审计",
    value: summary.value.audit_error_count,
    suggestion: summary.value.audit_error_count > 0 ? "优先查看审计日志中的错误记录" : "当前无错误记录",
  },
  {
    name: "资产沉淀",
    value: summary.value.asset_count,
    suggestion: summary.value.asset_count === 0 ? "发布指标、数据集或看板后会进入数据目录" : "持续复用已发布资产",
  },
])

const fetchSummary = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/operations/summary")
    summary.value = response.data
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.toolbar h2,
.ops-section h3 {
  margin: 0;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.metric-tile {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
}

.metric-tile span {
  color: var(--app-text-muted);
}

.metric-tile strong {
  font-size: 28px;
  color: var(--app-text);
}

.ops-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
