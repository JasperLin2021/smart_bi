<template>
  <el-card class="pinned-chart-card" :class="{ 'has-filter': (activeFilters?.length ?? 0) > 0 }">
    <template #header>
      <div class="card-header">
        <div class="card-title">
          <span>{{ chart.title }}</span>
          <el-tooltip v-if="chart.description" :content="chart.description" placement="top">
            <el-icon class="info-icon"><InfoFilled /></el-icon>
          </el-tooltip>
          <el-tag
            v-if="isFiltered"
            size="small"
            type="warning"
            effect="plain"
            class="filter-active-tag"
          >已过滤</el-tag>
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
    <div v-if="isKpi && displayRows.length > 0" class="kpi-body">
      <span class="kpi-label">{{ kpiLabel }}</span>
      <strong>{{ kpiValue }}</strong>
      <span class="kpi-meta">{{ displayRows.length }} 行数据</span>
    </div>
    <el-table v-else-if="isTable && displayRows.length > 0" :data="tableRows" size="small" class="table-body" max-height="280">
      <el-table-column
        v-for="column in tableColumns"
        :key="column"
        :prop="column"
        :label="column"
        min-width="120"
        show-overflow-tooltip
      />
    </el-table>
    <div v-else-if="displayRows.length > 0" ref="chartRef" class="chart-body"></div>
    <el-empty v-else :description="isFiltered ? '当前过滤条件下无数据' : '暂无数据'" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue"
import { InfoFilled, MoreFilled, Delete } from "@element-plus/icons-vue"
import * as echarts from "echarts"
import {
  CHART_COLOR_PALETTE,
  PRIMARY_CHART_COLOR,
  chartColorAt,
  colorizeCategoryData,
  makeAreaGradient,
} from "@/utils/chartColors"

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, any>>
}

interface CrossFilter {
  field: string
  value: any
}

const props = defineProps<{
  chart: PinnedChartData
  activeFilters?: CrossFilter[]
}>()

const emit = defineEmits<{
  delete: [id: number]
  filter: [filter: CrossFilter]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const normalizedChartType = computed(() => props.chart.chart_type || "bar")
const isTable = computed(() => normalizedChartType.value === "table")
const isKpi = computed(() => normalizedChartType.value === "kpi")
const isEChartsChart = computed(() => !isTable.value && !isKpi.value)

const isNumericValue = (value: unknown) =>
  typeof value === "number" || (value !== null && value !== "" && !Number.isNaN(Number(value)))

// Cross-filter: apply active filters from sibling charts to this chart's rows
const displayRows = computed(() => {
  const filters = props.activeFilters || []
  if (!filters.length) return props.chart.rows
  return props.chart.rows.filter(row =>
    filters.every(f => String(row[f.field]) === String(f.value))
  )
})

const isFiltered = computed(() =>
  (props.activeFilters || []).length > 0 && displayRows.value.length < props.chart.rows.length
)

// 识别数值列（基于原始数据，不受过滤影响，保证字段识别稳定）
const numericColumns = computed(() => {
  if (!props.chart.rows?.length) return []
  return props.chart.columns.filter(col => {
    return props.chart.rows.some(row => isNumericValue(row[col]))
  })
})

const dimensionColumns = computed(() => props.chart.columns.filter(col => !numericColumns.value.includes(col)))
const tableColumns = computed(() => props.chart.columns.slice(0, 10))
const tableRows = computed(() => displayRows.value.slice(0, 100))

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
  const total = displayRows.value.reduce((sum, row) => sum + (Number(row[field]) || 0), 0)
  return formatValue(total)
})

const buildOption = () => {
  const xAxisField = getXAxisField()
  const yAxisField = getYAxisField()
  const rows = displayRows.value

  if (!xAxisField || !yAxisField || !rows.length) return null

  const chartType = normalizedChartType.value
  const sortOrder = props.chart.sort_order

  // 饼图/环形图：ECharts 自动使用 color 数组为每个扇区着色
  if (chartType === "pie" || chartType === "donut") {
    let data = rows.map(row => ({
      name: String(row[xAxisField]),
      value: Number(row[yAxisField]) || 0
    }))
    if (sortOrder === "desc") data.sort((a, b) => b.value - a.value)
    else if (sortOrder === "asc") data.sort((a, b) => a.value - b.value)

    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        type: "pie",
        radius: chartType === "donut" ? ["38%", "68%"] : "68%",
        data: data.slice(0, 15),
        itemStyle: { borderRadius: 4, borderWidth: 1, borderColor: "#fff" },
      }]
    }
  }

  if (chartType === "funnel") {
    let data = rows.map(row => ({
      name: String(row[xAxisField]),
      value: Number(row[yAxisField]) || 0
    }))
    data.sort((a, b) => b.value - a.value)
    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        type: "funnel",
        left: "10%", width: "80%",
        minSize: "0%", maxSize: "100%",
        sort: "descending",
        gap: 2,
        label: { show: true, position: "inside", formatter: "{b}\n{d}%" },
        itemStyle: { borderWidth: 1, borderColor: "#fff" },
        data,
      }]
    }
  }

  if (chartType === "gauge") {
    const total = rows.reduce((s, r) => s + (Number(r[yAxisField]) || 0), 0)
    const maxVal = Math.max(...rows.map(r => Number(r[yAxisField]) || 0))
    const displayVal = rows.length === 1 ? Number(rows[0][yAxisField]) || 0 : total
    const gaugeMax = rows.length === 1 ? maxVal * 1.5 || 100 : maxVal * rows.length * 1.2 || 100
    return {
      series: [{
        type: "gauge",
        startAngle: 200, endAngle: -20,
        min: 0, max: Math.ceil(gaugeMax),
        radius: "85%",
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 18,
            color: [[0.3, "#67C23A"], [0.7, "#E6A23C"], [1, "#F56C6C"]]
          }
        },
        pointer: { itemStyle: { color: "auto" } },
        axisTick: { show: false },
        splitLine: { length: 12, lineStyle: { width: 2, color: "#999" } },
        axisLabel: { distance: 25, fontSize: 11 },
        detail: {
          valueAnimation: true,
          fontSize: 22,
          fontWeight: "bold",
          color: "auto",
          formatter: (val: number) => new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(val),
          offsetCenter: [0, "65%"]
        },
        title: { offsetCenter: [0, "88%"], fontSize: 12, color: "#999" },
        data: [{ value: displayVal, name: yAxisField }]
      }]
    }
  }

  if (chartType === "scatter") {
    const xField = numericColumns.value.length > 1 ? numericColumns.value[0] : xAxisField
    const yField = numericColumns.value.length > 1 ? numericColumns.value[1] : yAxisField
    const xIsNumeric = numericColumns.value.includes(xField)
    return {
      color: CHART_COLOR_PALETTE,
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
        data: rows.map((row, index) => ({
          value: [
            xIsNumeric ? Number(row[xField]) || 0 : String(row[xField]),
            Number(row[yField]) || 0
          ],
          itemStyle: { color: rows.length > 1 ? chartColorAt(index) : PRIMARY_CHART_COLOR }
        })),
      }]
    }
  }

  // 柱状图/条形图/折线图/面积图/组合图
  let dataPoints = rows.map(r => ({
    x: String(r[xAxisField]),
    y: Number(r[yAxisField]) || 0
  }))

  if (sortOrder === "desc") dataPoints.sort((a, b) => b.y - a.y)
  else if (sortOrder === "asc") dataPoints.sort((a, b) => a.y - b.y)

  // 条形图：多项时每条不同颜色
  if (chartType === "horizontal_bar") {
    return {
      color: CHART_COLOR_PALETTE,
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
        data: colorizeCategoryData(dataPoints.map(d => d.y), [0, 3, 3, 0]),
      }]
    }
  }

  if (chartType === "combo") {
    const secondaryField = getSecondaryYAxisField()
    const rowByX = new Map(rows.map(row => [String(row[xAxisField]), row]))
    const lineData = dataPoints.map(point => Number(rowByX.get(point.x)?.[secondaryField]) || 0)
    return {
      color: CHART_COLOR_PALETTE,
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
        { name: yAxisField, type: "bar", data: colorizeCategoryData(dataPoints.map(d => d.y), [3, 3, 0, 0]) },
        {
          name: secondaryField,
          type: "line",
          smooth: true,
          data: lineData,
          itemStyle: { color: chartColorAt(1) },
          lineStyle: { width: 2, color: chartColorAt(1) }
        }
      ]
    }
  }

  // 柱状图按分类项上色；折线/面积图保留主线颜色，仅点位轮换色
  const isBar = chartType === "bar"
  const primaryColor = PRIMARY_CHART_COLOR
  const values = dataPoints.map(d => d.y)

  return {
    color: CHART_COLOR_PALETTE,
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
      data: colorizeCategoryData(values, isBar ? [3, 3, 0, 0] : undefined),
      smooth: chartType === "line" || chartType === "area",
      lineStyle: chartType !== "bar" ? { width: 2, color: primaryColor } : undefined,
      areaStyle: chartType === "area" ? { color: makeAreaGradient(primaryColor) } : undefined,
    }]
  }
}

const applyOption = () => {
  if (!chartInstance) return
  const option = buildOption()
  if (option) {
    chartInstance.clear()
    chartInstance.setOption(option)
  }
}

let rafId: number | null = null

const initChart = () => {
  if (!isEChartsChart.value || !chartRef.value || !displayRows.value.length) {
    chartInstance?.dispose()
    chartInstance = null
    return
  }

  const el = chartRef.value
  if (el.offsetWidth === 0 || el.offsetHeight === 0) {
    // Container not ready yet — retry next frame
    rafId = requestAnimationFrame(initChart)
    return
  }

  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }

  if (!chartInstance) {
    chartInstance = echarts.init(el)
    chartInstance.on("click", (params: any) => {
      const xField = getXAxisField()
      if (!xField) return
      const value = params.name ?? params.value?.[0]
      if (value !== undefined && value !== null) {
        emit("filter", { field: xField, value: String(value) })
      }
    })
  }
  applyOption()
}

const renderChart = async () => {
  await nextTick()
  initChart()
}

const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  } else {
    initChart()
  }
}

let ro: ResizeObserver | null = null

const initObserver = () => {
  if (!chartRef.value || ro) return
  ro = new ResizeObserver(() => {
    if (!chartRef.value) return
    if (chartInstance) {
      chartInstance.resize()
    } else {
      initChart()
    }
  })
  ro.observe(chartRef.value)
}

// 用独立 computed 追踪真正影响渲染的字段，避免父组件无关重渲染触发 ECharts 重绘
const chartKey = computed(() =>
  `${props.chart.chart_type}|${props.chart.sort_order}|${props.chart.rows.length}|${props.chart.columns.join(",")}|${(props.activeFilters || []).map(f => `${f.field}=${f.value}`).join(";")}`
)
watch(chartKey, () => renderChart())

watch(chartRef, (el) => {
  if (el) {
    initObserver()
    renderChart()
  }
})

onMounted(() => {
  initObserver()
  renderChart()
  window.addEventListener("resize", resizeChart)
})

onBeforeUnmount(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
  ro?.disconnect()
  ro = null
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

.filter-active-tag {
  cursor: default;
}

.has-filter {
  border-color: rgba(217, 119, 6, 0.4) !important;
}
</style>
