<template>
  <el-drawer
    v-model="visible"
    title="预测分析"
    size="680px"
    direction="rtl"
    :destroy-on-close="true"
  >
    <div class="forecast-body">
      <el-form label-width="80px" size="small" class="forecast-form">
        <el-form-item label="预测周期">
          <el-input-number v-model="periods" :min="1" :max="24" style="width:120px" />
          <span class="hint">个数据点</span>
        </el-form-item>
        <el-form-item label="时间列">
          <el-input v-model="dateCol" placeholder="留空自动检测" style="width:180px" />
        </el-form-item>
        <el-form-item label="数值列">
          <el-input v-model="valueCol" placeholder="留空自动检测" style="width:180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="run">运行预测</el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="error" type="error" :title="error" :closable="false" style="margin-bottom:16px" />

      <div v-if="result" class="forecast-result">
        <div class="forecast-meta">
          <el-tag size="small">时间列: {{ result.date_col }}</el-tag>
          <el-tag size="small" type="success">数值列: {{ result.value_col }}</el-tag>
          <el-tag size="small" type="info">{{ histCount }}个历史点 + {{ forecastCount }}个预测点</el-tag>
        </div>
        <div ref="chartRef" class="forecast-chart"></div>
        <div class="forecast-table-wrap">
          <el-table :data="result.points" size="small" max-height="240">
            <el-table-column prop="label" label="时间" width="130" />
            <el-table-column prop="value" label="数值" width="120" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.is_forecast" size="small" type="warning">预测</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">历史</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <el-empty v-else-if="!loading && !error" description="点击运行预测生成时序预测图" :image-size="80" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import * as echarts from "@/utils/echarts"
import axios from "axios"

const props = defineProps<{
  datasourceId: number | null
  sqlQuery: string
  chartTitle?: string
}>()

const visible = defineModel<boolean>({ required: true })

const periods = ref(6)
const dateCol = ref("")
const valueCol = ref("")
const loading = ref(false)
const error = ref("")
const result = ref<{
  date_col: string
  value_col: string
  points: Array<{ label: string; value: number; is_forecast: boolean }>
} | null>(null)

const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const histCount = computed(() => result.value?.points.filter(p => !p.is_forecast).length ?? 0)
const forecastCount = computed(() => result.value?.points.filter(p => p.is_forecast).length ?? 0)

async function run() {
  if (!props.sqlQuery.trim()) {
    error.value = "SQL不能为空"
    return
  }
  loading.value = true
  error.value = ""
  result.value = null
  try {
    const resp = await axios.post("/api/forecast", {
      datasource_id: props.datasourceId,
      sql_query: props.sqlQuery,
      periods: periods.value,
      date_col: dateCol.value || null,
      value_col: valueCol.value || null,
    })
    result.value = resp.data
    await nextTick()
    renderChart()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "预测失败"
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !result.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)

  const points = result.value.points
  const labels = points.map(p => p.label)
  const histValues = points.map(p => (!p.is_forecast ? p.value : null))
  const forecastValues = points.map(p => (p.is_forecast ? p.value : null))

  // Connect historical to forecast
  const splitIdx = points.findIndex(p => p.is_forecast) - 1
  if (splitIdx >= 0 && splitIdx < points.length - 1) {
    forecastValues[splitIdx] = histValues[splitIdx]
  }

  chartInstance.setOption({
    grid: { left: 50, right: 20, top: 20, bottom: 36 },
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["历史", "预测"] },
    xAxis: { type: "category", data: labels, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: "value" },
    series: [
      {
        name: "历史",
        type: "line",
        data: histValues,
        smooth: true,
        connectNulls: false,
        itemStyle: { color: "#5470c6" },
        lineStyle: { width: 2 },
      },
      {
        name: "预测",
        type: "line",
        data: forecastValues,
        smooth: true,
        connectNulls: false,
        itemStyle: { color: "#ee6666" },
        lineStyle: { width: 2, type: "dashed" },
        symbol: "circle",
        symbolSize: 6,
      },
    ],
  })
}

watch(visible, (v) => {
  if (!v) {
    chartInstance?.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.forecast-body { padding: 4px 0; }
.forecast-form { margin-bottom: 12px; }
.hint { margin-left: 8px; color: var(--app-text-muted); font-size: 12px; }
.forecast-result { display: flex; flex-direction: column; gap: 12px; }
.forecast-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.forecast-chart { height: 300px; }
.forecast-table-wrap { max-height: 260px; overflow: hidden; }
</style>
