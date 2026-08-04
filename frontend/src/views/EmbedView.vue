<template>
  <div class="embed-shell">
    <div v-if="loading" class="embed-loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
    </div>

    <div v-else-if="error" class="embed-error">
      <el-icon :size="32"><Warning /></el-icon>
      <p>{{ error }}</p>
    </div>

    <template v-else-if="data">
      <div class="embed-header" v-if="!noHeader">
        <span class="embed-title">{{ data.title }}</span>
      </div>

      <div class="embed-body">
        <!-- Chart embed -->
        <template v-if="data.resource_type === 'chart'">
          <div v-if="data.rows && data.rows.length" ref="chartRef" class="embed-chart"></div>
          <el-empty v-else description="暂无数据" />
        </template>

        <!-- Dashboard embed (grid of live charts) -->
        <template v-else-if="data.resource_type === 'dashboard'">
          <div v-if="data.charts && data.charts.length" class="embed-dashboard-grid">
            <div v-for="chart in data.charts" :key="chart.resource_id" class="embed-dashboard-cell">
              <div class="embed-cell-title">{{ chart.title }}</div>
              <div v-if="chart.error" class="embed-cell-error">{{ chart.error }}</div>
              <el-empty v-else-if="!chart.rows || !chart.rows.length" description="暂无数据" :image-size="60" />
              <div v-else class="embed-cell-chart" :ref="(el) => setChartRef(chart.resource_id, el)"></div>
            </div>
          </div>
          <el-empty v-else description="该看板暂无图表" />
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick } from "vue"
import { useRoute } from "vue-router"
import * as echarts from "@/utils/echarts"
import { Loading, Warning } from "@element-plus/icons-vue"
import axios from "axios"
import {
  CHART_COLOR_PALETTE,
  PRIMARY_CHART_COLOR,
  chartColorAt,
  colorizeCategoryData,
  makeAreaGradient,
} from "@/utils/chartColors"

const route = useRoute()
const token = route.params.token as string
const noHeader = "no_header" in route.query

interface ChartData {
  resource_id: number
  title: string
  chart_type: string | null
  columns: string[]
  rows: Array<Record<string, any>>
  error?: string | null
}

const loading = ref(true)
const error = ref("")
const data = ref<{
  resource_type: string
  resource_id: number
  title: string
  chart_type: string | null
  columns: string[]
  rows: Array<Record<string, any>>
  charts: ChartData[]
} | null>(null)

const chartRef = ref<HTMLDivElement | null>(null)
// Dashboard mode: collect each cell's container element by chart id.
const dashboardChartEls = new Map<number, HTMLElement>()

function setChartRef(resourceId: number, el: any) {
  if (el) dashboardChartEls.set(resourceId, el as HTMLElement)
  else dashboardChartEls.delete(resourceId)
}

// 跟踪所有 echarts 实例，容器尺寸变化时 resize，卸载时统一 dispose
const chartInstances = new Map<HTMLElement, echarts.ECharts>()
let resizeObserver: ResizeObserver | null = null

function trackChartInstance(el: HTMLElement, instance: echarts.ECharts) {
  chartInstances.set(el, instance)
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chartInstances.get(entry.target as HTMLElement)?.resize()
      }
    })
  }
  resizeObserver.observe(el)
}

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  for (const instance of chartInstances.values()) instance.dispose()
  chartInstances.clear()
})

const API_BASE = import.meta.env.VITE_API_URL || "/api"

onMounted(async () => {
  try {
    const resp = await axios.get(`${API_BASE}/embed/public/${token}`)
    data.value = resp.data
    await nextTick()
    if (data.value?.resource_type === "chart" && data.value.rows.length) {
      if (chartRef.value) renderChartInto(chartRef.value, data.value as ChartData)
    } else if (data.value?.resource_type === "dashboard") {
      for (const chart of data.value.charts || []) {
        const el = dashboardChartEls.get(chart.resource_id)
        if (el && chart.rows && chart.rows.length) renderChartInto(el, chart)
      }
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "加载失败，embed token 可能无效或已过期"
  } finally {
    loading.value = false
  }
})

function renderChartInto(el: HTMLElement, source: ChartData) {
  const chartInstanceLocal = echarts.init(el)
  trackChartInstance(el, chartInstanceLocal)

  const rows = source.rows
  const columns = source.columns
  const chartType = source.chart_type || "bar"

  const isNumeric = (v: any) => typeof v === "number" || (!isNaN(Number(v)) && v !== null && v !== "")

  if (chartType === "pie" || chartType === "donut") {
    const nameCol = columns[0]
    const valCol = columns.find(c => c !== nameCol && isNumeric(rows[0]?.[c])) || columns[1]
    chartInstanceLocal.setOption({
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item" },
      series: [{
        type: "pie",
        radius: chartType === "donut" ? ["38%", "68%"] : "68%",
        data: rows.map(r => ({ name: r[nameCol], value: Number(r[valCol]) })),
        itemStyle: { borderRadius: 4, borderWidth: 1, borderColor: "#fff" },
      }],
    })
    return
  }

  const xCol = columns[0]
  const valCols = columns.slice(1).filter(c => isNumeric(rows[0]?.[c]))
  const seriesType = chartType === "line" || chartType === "area" ? "line" : "bar"
  const hasSingleValueSeries = valCols.length === 1
  chartInstanceLocal.setOption({
    color: CHART_COLOR_PALETTE,
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: rows.map(r => r[xCol]), axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: "value" },
    series: valCols.map((col, index) => {
      const color = hasSingleValueSeries ? PRIMARY_CHART_COLOR : chartColorAt(index)
      const values = rows.map(r => Number(r[col]))
      return {
        name: col,
        type: seriesType,
        data: hasSingleValueSeries ? colorizeCategoryData(values, seriesType === "bar" ? [3, 3, 0, 0] : undefined) : values,
        itemStyle: hasSingleValueSeries ? undefined : { color },
        lineStyle: seriesType === "line" ? { color, width: 2 } : undefined,
        areaStyle: chartType === "area" ? { color: makeAreaGradient(color) } : undefined,
      }
    }),
  })
}
</script>

<style scoped>
.embed-shell {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  font-family: system-ui, sans-serif;
}
.embed-loading, .embed-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  gap: 12px;
}
.embed-header {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  background: #fafafa;
}
.embed-title { font-weight: 600; font-size: 15px; }
.embed-body { flex: 1; padding: 16px; overflow: auto; }
.embed-chart { width: 100%; height: calc(100vh - 120px); }
.embed-dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}
.embed-dashboard-cell {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}
.embed-cell-title { font-weight: 600; font-size: 14px; margin-bottom: 8px; }
.embed-cell-chart { width: 100%; height: 260px; }
.embed-cell-error { color: #c0392b; font-size: 13px; padding: 24px 0; text-align: center; }
</style>
