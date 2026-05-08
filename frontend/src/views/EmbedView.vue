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

        <!-- Dashboard embed (simple card list) -->
        <template v-else-if="data.resource_type === 'dashboard'">
          <div class="embed-dashboard-info">
            <el-icon :size="48"><DataBoard /></el-icon>
            <p>{{ data.title }}</p>
            <p class="embed-sub">嵌入式看板 – 完整功能请在 Smart BI 中访问</p>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, nextTick } from "vue"
import { useRoute } from "vue-router"
import * as echarts from "echarts"
import { Loading, Warning, DataBoard } from "@element-plus/icons-vue"
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

const loading = ref(true)
const error = ref("")
const data = ref<{
  resource_type: string
  resource_id: number
  title: string
  chart_type: string | null
  columns: string[]
  rows: Array<Record<string, any>>
} | null>(null)

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const API_BASE = import.meta.env.VITE_API_URL || "/api"

onMounted(async () => {
  try {
    const resp = await axios.get(`${API_BASE}/embed/public/${token}`)
    data.value = resp.data
    await nextTick()
    if (data.value?.resource_type === "chart" && data.value.rows.length) {
      renderChart()
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "加载失败，embed token 可能无效或已过期"
  } finally {
    loading.value = false
  }
})

function renderChart() {
  if (!chartRef.value || !data.value) return
  chartInstance = echarts.init(chartRef.value)

  const rows = data.value.rows
  const columns = data.value.columns
  const chartType = data.value.chart_type || "bar"

  const isNumeric = (v: any) => typeof v === "number" || (!isNaN(Number(v)) && v !== null && v !== "")

  if (chartType === "pie" || chartType === "donut") {
    const nameCol = columns[0]
    const valCol = columns.find(c => c !== nameCol && isNumeric(rows[0]?.[c])) || columns[1]
    chartInstance.setOption({
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
  chartInstance.setOption({
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
.embed-dashboard-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #888;
  gap: 12px;
}
.embed-sub { font-size: 12px; color: #aaa; }
</style>
