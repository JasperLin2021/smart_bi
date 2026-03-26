<template>
  <div class="page">
    <!-- 固定图表区域 -->
    <div v-if="pinnedCharts.length > 0">
      <div class="section-title">
        我的图表
        <el-tag size="small" type="info">{{ pinnedCharts.length }} 个</el-tag>
      </div>
      <el-row :gutter="16">
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

    <!-- 空状态提示 -->
    <div v-if="pinnedCharts.length === 0" class="empty-state">
      <el-empty description="暂无图表，请在智能问数中固定图表到此处" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import PinnedChartCard from "@/components/PinnedChartCard.vue"
import { useDatasourceStore } from "@/store/datasource"

const datasourceStore = useDatasourceStore()

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

const fetchPinnedCharts = async () => {
  try {
    const params: Record<string, any> = {}
    if (datasourceStore.currentId) params.datasource_id = datasourceStore.currentId
    const response = await axios.get("/api/pinned-charts/with-data", { params })
    pinnedCharts.value = response.data
  } catch (error) {
    console.error("固定图表加载失败", error)
  }
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

// Reload when datasource changes
watch(() => datasourceStore.currentId, () => {
  fetchPinnedCharts()
})

onMounted(() => {
  fetchPinnedCharts()
})
</script>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.chart-col {
  margin-bottom: 16px;
}
</style>
