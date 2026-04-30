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
    <div v-if="isKpi && chart.rows.length > 0" class="kpi-body">
      <span class="kpi-label">{{ kpiLabel }}</span>
      <strong>{{ kpiValue }}</strong>
      <span class="kpi-meta">{{ chart.rows.length }} 行数据</span>
    </div>
    <el-table v-else-if="isTable && chart.rows.length > 0" :data="tableRows" size="small" class="table-body" max-height="280">
      <el-table-column
        v-for="column in tableColumns"
        :key="column"
        :prop="column"
        :label="column"
        min-width="120"
        show-overflow-tooltip
      />
    </el-table>
    <div v-else-if="chart.rows.length > 0" ref="chartRef" class="chart-body"></div>
    <el-empty v-else description="暂无数据" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue"
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
const resizeChart = () => chartInstance?.resize()

const normalizedChartType = computed(() => props.chart.chart_type || "bar")
const isTable = computed(() => normalizedChartType.value === "table")
const isKpi = computed(() => normalizedChartType.value === "kpi")
const isEChartsChart = computed(() => !isTable.value && !isKpi.value)

const isNumericValue = (value: unknown) =>
  typeof value === "number" || (value !== null && value !== "" && !Number.isNaN(Number(value)))

// 识别数值列
const numericColumns = computed(() => {
  if (!props.chart.rows?.length) return []
  return props.chart.columns.filter(col => {
    return props.chart.rows.some(row => isNumericValue(row[col]))
  })
})

const dimensionColumns = computed(() => props.chart.columns.filter(col => !numericColumns.value.includes(col)))
const tableColumns = computed(() => props.chart.columns.slice(0, 10))
const tableRows = computed(() => props.chart.rows.slice(0, 100))

// 自动选择字段
const getXAxisField = () => {
  const dateFields = ["stat_date", "date", "time", "day", "month"]
  return props.chart.columns.find(c => dateFields.some(d => c.toLowerCase().includes(d))) ||
    dimensionColumns.value[0] ||
    props.chart.columns[0]
}

const getYAxisField = () => {
  const valueFields = ["count", "total", "sum", "occurrence", "times", "amount"]
  return numericColumns.value.find(c => valueFields.some(v => c.toLowerCase().includes(v))) || numericColumns.value[0] || ""
}

const getSecondaryYAxisField = () => numericColumns.value.find(col => col !== getYAxisField()) || getYAxisField()

const formatValue = (value: number) => new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value)

const kpiLabel = computed(() => getYAxisField() || props.chart.columns[0] || "指标")

const kpiValue = computed(() => {
  const field = getYAxisField()
  if (!field) return "-"
  const total = props.chart.rows.reduce((sum, row) => sum + (Number(row[field]) || 0), 0)
  return formatValue(total)
})

const buildOption = () => {
  const xAxisField = getXAxisField()
  const yAxisField = getYAxisField()
  
  if (!xAxisField || !yAxisField || !props.chart.rows?.length) return null

  const chartType = normalizedChartType.value
  const sortOrder = props.chart.sort_order

  // 饼图/环形图
  if (chartType === "pie" || chartType === "donut") {
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
        radius: chartType === "donut" ? ["38%", "68%"] : "68%",
        data: data.slice(0, 15)
      }]
    }
  }

  if (chartType === "scatter") {
    const xField = numericColumns.value.length > 1 ? numericColumns.value[0] : xAxisField
    const yField = numericColumns.value.length > 1 ? numericColumns.value[1] : yAxisField
    const xIsNumeric = numericColumns.value.includes(xField)
    return {
      tooltip: { trigger: "item" },
      grid: { top: 24, bottom: 50, left: 54, right: 24 },
      xAxis: {
        type: xIsNumeric ? "value" : "category",
        name: xField,
        axisLabel: { rotate: xIsNumeric ? 0 : 45, fontSize: 11 }
      },
      yAxis: { type: "value", name: yField },
      series: [{
        type: "scatter",
        symbolSize: 10,
        data: props.chart.rows.map(row => [
          xIsNumeric ? Number(row[xField]) || 0 : String(row[xField]),
          Number(row[yField]) || 0
        ]),
        itemStyle: { color: "#0f766e" }
      }]
    }
  }

  // 柱状图/条形图/折线图/面积图/组合图
  let dataPoints = props.chart.rows.map(r => ({
    x: String(r[xAxisField]),
    y: Number(r[yAxisField]) || 0
  }))
  
  if (sortOrder === "desc") dataPoints.sort((a, b) => b.y - a.y)
  else if (sortOrder === "asc") dataPoints.sort((a, b) => a.y - b.y)

  if (chartType === "horizontal_bar") {
    return {
      tooltip: { trigger: "axis" },
      grid: { top: 20, bottom: 30, left: 82, right: 24 },
      xAxis: { type: "value" },
      yAxis: {
        type: "category",
        data: dataPoints.map(d => d.x),
        axisLabel: { fontSize: 11 }
      },
      series: [{
        type: "bar",
        data: dataPoints.map(d => d.y),
        itemStyle: { color: "#0f766e" }
      }]
    }
  }

  if (chartType === "combo") {
    const secondaryField = getSecondaryYAxisField()
    const rowByX = new Map(props.chart.rows.map(row => [String(row[xAxisField]), row]))
    const lineData = dataPoints.map(point => Number(rowByX.get(point.x)?.[secondaryField]) || 0)
    return {
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { top: 46, bottom: 50, left: 50, right: 20 },
      xAxis: {
        type: "category",
        data: dataPoints.map(d => d.x),
        axisLabel: { rotate: dataPoints.length > 8 ? 45 : 0, fontSize: 11 }
      },
      yAxis: { type: "value" },
      series: [
        { name: yAxisField, type: "bar", data: dataPoints.map(d => d.y), itemStyle: { color: "#0f766e" } },
        { name: secondaryField, type: "line", smooth: true, data: lineData, itemStyle: { color: "#b7791f" } }
      ]
    }
  }
  
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
      type: chartType === "area" ? "line" : chartType,
      data: dataPoints.map(d => d.y),
      smooth: chartType === "line" || chartType === "area",
      areaStyle: chartType === "area" ? {} : undefined,
      itemStyle: { color: "#0f766e" }
    }]
  }
}

const renderChart = async () => {
  await nextTick()
  if (!isEChartsChart.value || !chartRef.value || !props.chart.rows.length) {
    chartInstance?.dispose()
    chartInstance = null
    return
  }
  
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
  window.addEventListener("resize", resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart)
  chartInstance?.dispose()
})
</script>

<style scoped>
.pinned-chart-card {
  height: 100%;
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-soft);
  transition: border-color var(--app-transition), box-shadow var(--app-transition);
}

.pinned-chart-card:hover {
  transform: none;
  border-color: rgba(15, 118, 110, 0.28);
  box-shadow: var(--app-shadow-hover);
}

.pinned-chart-card :deep(.el-card__header) {
  padding: 12px 14px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
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

.table-body {
  width: 100%;
}

.kpi-body {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding: 20px;
}

.kpi-label {
  color: var(--app-text-muted);
  font-size: 13px;
}

.kpi-body strong {
  color: var(--app-text);
  font-size: 36px;
  line-height: 1.1;
}

.kpi-meta {
  color: var(--app-text-muted);
  font-size: 12px;
}
</style>
