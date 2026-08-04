<template>
  <div class="share-shell">
    <div v-if="loading" class="share-status">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
    </div>

    <div v-else-if="error" class="share-status">
      <el-icon :size="32" color="#c0392b"><Warning /></el-icon>
      <p>{{ error }}</p>
    </div>

    <template v-else-if="data">
      <header class="share-header">
        <span class="share-title">{{ data.title || "公开看板" }}</span>
        <span class="share-badge">公开分享</span>
      </header>

      <main class="share-body">
        <div v-if="data.charts && data.charts.length" class="share-grid">
          <section v-for="chart in data.charts" :key="chart.resource_id" class="share-cell">
            <div class="share-cell-title">{{ chart.title }}</div>
            <div v-if="chart.error" class="share-cell-error">{{ chart.error }}</div>
            <el-empty v-else-if="!chart.rows || !chart.rows.length" description="暂无数据" :image-size="60" />
            <div v-else class="share-cell-chart" :ref="(el) => setChartRef(chart.resource_id, el)"></div>
          </section>
        </div>
        <el-empty v-else description="该看板暂无图表" />
      </main>
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
const data = ref<{ title: string; charts: ChartData[] } | null>(null)

// 看板模式下按图表 id 收集容器元素，渲染后统一管理 resize / dispose
const chartEls = new Map<number, HTMLElement>()
const chartInstances = new Map<HTMLElement, echarts.ECharts>()
let resizeObserver: ResizeObserver | null = null

function setChartRef(resourceId: number, el: any) {
  if (el) chartEls.set(resourceId, el as HTMLElement)
  else chartEls.delete(resourceId)
}

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

onMounted(async () => {
  try {
    const resp = await axios.get(`/api/dashboards/public/${token}/data`)
    data.value = resp.data
    await nextTick()
    for (const chart of data.value?.charts || []) {
      const el = chartEls.get(chart.resource_id)
      if (el && chart.rows && chart.rows.length) renderChartInto(el, chart)
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "加载失败，分享链接可能无效或看板已取消公开"
  } finally {
    loading.value = false
  }
})

function renderChartInto(el: HTMLElement, source: ChartData) {
  const instance = echarts.init(el)
  trackChartInstance(el, instance)

  const rows = source.rows
  const columns = source.columns
  const chartType = source.chart_type || "bar"

  const isNumeric = (v: any) => typeof v === "number" || (!isNaN(Number(v)) && v !== null && v !== "")

  if (chartType === "pie" || chartType === "donut") {
    const nameCol = columns[0]
    const valCol = columns.find((c) => c !== nameCol && isNumeric(rows[0]?.[c])) || columns[1]
    instance.setOption({
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: chartType === "donut" ? ["38%", "68%"] : "68%",
          data: rows.map((r) => ({ name: r[nameCol], value: Number(r[valCol]) })),
          itemStyle: { borderRadius: 4, borderWidth: 1, borderColor: "#fff" },
        },
      ],
    })
    return
  }

  const xCol = columns[0]
  const valCols = columns.slice(1).filter((c) => isNumeric(rows[0]?.[c]))
  const seriesType = chartType === "line" || chartType === "area" ? "line" : "bar"
  const hasSingleValueSeries = valCols.length === 1
  instance.setOption({
    color: CHART_COLOR_PALETTE,
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: rows.map((r) => r[xCol]), axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: "value" },
    series: valCols.map((col, index) => {
      const color = hasSingleValueSeries ? PRIMARY_CHART_COLOR : chartColorAt(index)
      const values = rows.map((r) => Number(r[col]))
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
.share-shell {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  font-family: system-ui, -apple-system, sans-serif;
}
.share-status {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  gap: 12px;
}
.share-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}
.share-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.share-badge {
  font-size: 12px;
  color: #67c23a;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 10px;
  padding: 2px 10px;
}
.share-body {
  flex: 1;
  padding: 24px;
  overflow: auto;
}
.share-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}
.share-cell {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.share-cell-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
  color: #303133;
}
.share-cell-chart {
  width: 100%;
  height: 280px;
}
.share-cell-error {
  color: #c0392b;
  font-size: 13px;
  padding: 32px 0;
  text-align: center;
}
</style>
