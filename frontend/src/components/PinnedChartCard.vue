<template>
  <el-card class="pinned-chart-card">
    <template #header>
      <div class="card-header">
        <div class="card-title">
          <span>{{ chart.title }}</span>
          <el-tooltip v-if="chart.description" :content="chart.description" placement="top">
            <el-icon class="info-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="card-actions">
          <el-dropdown trigger="click">
            <el-button size="small" text>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$emit('delete', chart.id)">
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </template>
    <div v-if="chart.rows.length > 0" ref="chartRef" class="chart-body"></div>
    <el-empty v-else description="暂无数据" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, nextTick } from "vue"
import { InfoFilled, MoreFilled, Delete } from "@element-plus/icons-vue"
import * as echarts from "echarts"

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, any>>
}

const props = defineProps<{
  chart: PinnedChartData
}>()

defineEmits<{
  delete: [id: number]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

// 识别数值列
const getNumericColumns = () => {
  if (!props.chart.rows?.length) return []
  return props.chart.columns.filter(col => {
    const val = props.chart.rows[0][col]
    return typeof val === "number" || (!isNaN(Number(val)) && val !== null && val !== "")
  })
}

// 自动选择字段
const getXAxisField = () => {
  const dateFields = ["stat_date", "date", "time", "day", "month"]
  return props.chart.columns.find(c => dateFields.some(d => c.toLowerCase().includes(d))) || props.chart.columns[0]
}

const getYAxisField = () => {
  const numericCols = getNumericColumns()
  const valueFields = ["count", "total", "sum", "occurrence", "times", "amount"]
  return numericCols.find(c => valueFields.some(v => c.toLowerCase().includes(v))) || numericCols[0] || ""
}

const buildOption = () => {
  const xAxisField = getXAxisField()
  const yAxisField = getYAxisField()
  
  if (!xAxisField || !yAxisField || !props.chart.rows?.length) return null

  const chartType = props.chart.chart_type
  const sortOrder = props.chart.sort_order

  // 饼图
  if (chartType === "pie") {
    let data = props.chart.rows.map(row => ({
      name: String(row[xAxisField]),
      value: Number(row[yAxisField]) || 0
    }))
    if (sortOrder === "desc") data.sort((a, b) => b.value - a.value)
    else if (sortOrder === "asc") data.sort((a, b) => a.value - b.value)
    
    return {
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        type: "pie",
        radius: ["30%", "60%"],
        data: data.slice(0, 15)
      }]
    }
  }

  // 柱状图/折线图
  let dataPoints = props.chart.rows.map(r => ({
    x: String(r[xAxisField]),
    y: Number(r[yAxisField]) || 0
  }))
  
  if (sortOrder === "desc") dataPoints.sort((a, b) => b.y - a.y)
  else if (sortOrder === "asc") dataPoints.sort((a, b) => a.y - b.y)
  
  return {
    tooltip: { trigger: "axis" },
    grid: { top: 20, bottom: 50, left: 50, right: 20 },
    xAxis: { 
      type: "category", 
      data: dataPoints.map(d => d.x),
      axisLabel: { rotate: dataPoints.length > 8 ? 45 : 0, fontSize: 11 }
    },
    yAxis: { type: "value" },
    series: [{
      type: chartType,
      data: dataPoints.map(d => d.y),
      itemStyle: { color: "#409eff" }
    }]
  }
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value || !props.chart.rows.length) return
  
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  
  const option = buildOption()
  if (option) {
    chartInstance.clear()
    chartInstance.setOption(option)
  }
}

watch(() => props.chart, () => renderChart(), { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener("resize", () => chartInstance?.resize())
})
</script>

<style scoped>
.pinned-chart-card {
  height: 100%;
  border: none;
  box-shadow: var(--app-shadow-soft);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.pinned-chart-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(6, 182, 212, 0.15);
}

.pinned-chart-card :deep(.el-card__header) {
  padding: 16px 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid var(--app-border-light);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: var(--app-text);
}

.info-icon {
  color: var(--app-text-light);
  cursor: pointer;
  transition: color 0.2s;
}

.info-icon:hover {
  color: var(--app-primary);
}

.card-actions :deep(.el-button) {
  color: var(--app-text-light);
}

.card-actions :deep(.el-button:hover) {
  color: var(--app-primary);
}

.chart-body {
  width: 100%;
  height: 280px;
  padding: 8px;
}
</style>
