<template>
  <el-card v-if="hasData">
    <template #header>
      <div class="card-header">
        <span class="card-header-title">数据可视化</span>
        <div class="card-header-actions">
          <el-select v-model="chartType" size="small" style="width: 100px; margin-right: 8px;">
            <el-option label="折线图" value="line" />
            <el-option label="柱状图" value="bar" />
            <el-option label="面积图" value="area" />
            <el-option label="饼图" value="pie" />
            <el-option label="漏斗图" value="funnel" />
            <el-option label="仪表盘" value="gauge" />
          </el-select>
          <el-select v-model="xAxisField" size="small" placeholder="X轴" style="width: 120px; margin-right: 8px;">
            <el-option v-for="col in columns" :key="col" :label="col" :value="col" />
          </el-select>
          <el-select v-model="yAxisField" size="small" placeholder="Y轴" style="width: 120px; margin-right: 8px;">
            <el-option v-for="col in numericColumns" :key="col" :label="col" :value="col" />
          </el-select>
          <el-select v-model="seriesField" size="small" placeholder="分组(可选)" clearable style="width: 120px; margin-right: 8px;">
            <el-option v-for="col in categoryColumns" :key="col" :label="col" :value="col" />
          </el-select>
          <el-button size="small" @click="exportPng">导出PNG</el-button>
        </div>
      </div>
    </template>
    <div ref="chartRef" style="width: 100%; height: 400px;"></div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from "vue"
import * as echarts from "echarts"
import {
  CHART_COLOR_PALETTE,
  PRIMARY_CHART_COLOR,
  chartColorAt,
  colorizeCategoryData,
  makeAreaGradient,
} from "@/utils/chartColors"

const props = defineProps<{
  columns: string[]
  rows: Array<Record<string, any>>
}>()

const chartRef = ref<HTMLDivElement | null>(null)
const chartType = ref<"line" | "bar" | "area" | "pie" | "funnel" | "gauge">("line")
const xAxisField = ref("")
const yAxisField = ref("")
const seriesField = ref("")
let chartInstance: echarts.ECharts | null = null

const hasData = computed(() => props.rows && props.rows.length > 0)

// 识别数值列
const numericColumns = computed(() => {
  if (!props.rows?.length) return []
  return props.columns.filter(col => {
    const val = props.rows[0][col]
    return typeof val === "number" || (!isNaN(Number(val)) && val !== null && val !== "")
  })
})

// 识别分类列（非数值且唯一值较少）
const categoryColumns = computed(() => {
  if (!props.rows?.length) return []
  return props.columns.filter(col => {
    const uniqueValues = new Set(props.rows.map(r => r[col]))
    return uniqueValues.size > 1 && uniqueValues.size <= 50 && !numericColumns.value.includes(col)
  })
})

// 自动推断字段
const autoDetectFields = () => {
  if (!props.columns?.length) return
  
  // X轴：优先选择日期/时间类型的字段（基于数据内容检测）
  const isDateLike = (col: string) => {
    const val = String(props.rows[0]?.[col] ?? "")
    // Check common date patterns: 2024-01-01, 2024/01/01, 20240101, etc.
    return /^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(val) || /date|time|day|month|year|week/i.test(col)
  }
  xAxisField.value = props.columns.find(c => isDateLike(c)) || props.columns.find(c => !numericColumns.value.includes(c)) || props.columns[0]

  // Y轴：选择第一个数值列
  yAxisField.value = numericColumns.value[0] || ""

  // 分组字段：选择非X轴的低基数分类列
  seriesField.value = categoryColumns.value.find(c => c !== xAxisField.value) || ""
}

// 构建图表配置
const buildOption = () => {
  if (!xAxisField.value || !yAxisField.value || !props.rows?.length) return null

  // 饼图特殊处理
  if (chartType.value === "pie") {
    const data = props.rows.map(row => ({
      name: String(row[xAxisField.value]),
      value: Number(row[yAxisField.value]) || 0
    }))
    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      legend: { orient: "vertical", left: "left", top: "center" },
      series: [{
        type: "pie",
        radius: ["40%", "70%"],
        data: data.slice(0, 20), // 限制饼图数量
        itemStyle: { borderRadius: 4, borderWidth: 1, borderColor: "#fff" },
      }]
    }
  }

  if (chartType.value === "funnel") {
    const data = props.rows.map(row => ({
      name: String(row[xAxisField.value]),
      value: Number(row[yAxisField.value]) || 0
    })).sort((a, b) => b.value - a.value)
    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        type: "funnel",
        left: "10%", width: "80%",
        sort: "descending", gap: 2,
        label: { show: true, position: "inside", formatter: "{b}\n{d}%" },
        itemStyle: { borderWidth: 1, borderColor: "#fff" },
        data,
      }]
    }
  }

  if (chartType.value === "gauge") {
    const rows = props.rows
    const displayVal = rows.length === 1
      ? Number(rows[0][yAxisField.value]) || 0
      : rows.reduce((s, r) => s + (Number(r[yAxisField.value]) || 0), 0)
    const maxVal = Math.max(...rows.map(r => Number(r[yAxisField.value]) || 0))
    const gaugeMax = Math.ceil((rows.length === 1 ? maxVal * 1.5 : maxVal * rows.length * 1.2) || 100)
    return {
      series: [{
        type: "gauge",
        startAngle: 200, endAngle: -20,
        min: 0, max: gaugeMax,
        radius: "85%", splitNumber: 5,
        axisLine: {
          lineStyle: { width: 18, color: [[0.3, "#67C23A"], [0.7, "#E6A23C"], [1, "#F56C6C"]] }
        },
        pointer: { itemStyle: { color: "auto" } },
        axisTick: { show: false },
        splitLine: { length: 12, lineStyle: { width: 2, color: "#999" } },
        axisLabel: { distance: 25, fontSize: 11 },
        detail: {
          valueAnimation: true, fontSize: 22, fontWeight: "bold", color: "auto",
          formatter: (val: number) => new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(val),
          offsetCenter: [0, "65%"]
        },
        title: { offsetCenter: [0, "88%"], fontSize: 12, color: "#999" },
        data: [{ value: displayVal, name: yAxisField.value }]
      }]
    }
  }

  // 折线图/柱状图/面积图
  if (seriesField.value) {
    // 多系列模式
    const seriesValues = [...new Set(props.rows.map(r => r[seriesField.value]))]
    const xValues = [...new Set(props.rows.map(r => String(r[xAxisField.value])))]
    
    const series = seriesValues.map((sv, index) => {
      const color = chartColorAt(index)
      const seriesData = xValues.map(xv => {
        const row = props.rows.find(r => 
          String(r[xAxisField.value]) === xv && r[seriesField.value] === sv
        )
        return row ? Number(row[yAxisField.value]) || 0 : 0
      })
      return {
        name: String(sv),
        type: chartType.value === "area" ? "line" : chartType.value,
        data: seriesData,
        smooth: true,
        itemStyle: { color },
        lineStyle: chartType.value !== "bar" ? { color, width: 2 } : undefined,
        areaStyle: chartType.value === "area" ? { color: makeAreaGradient(color) } : undefined
      }
    })

    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "axis" },
      legend: { 
        data: seriesValues.map(String),
        type: "scroll",
        top: 0
      },
      grid: { top: 60, bottom: 60, left: 60, right: 30 },
      xAxis: { 
        type: "category", 
        data: xValues,
        axisLabel: { rotate: xValues.length > 10 ? 45 : 0 }
      },
      yAxis: { type: "value" },
      series
    }
  } else {
    // 单系列模式
    const xData = props.rows.map(r => String(r[xAxisField.value]))
    const yData = props.rows.map(r => Number(r[yAxisField.value]) || 0)
    const isBar = chartType.value === "bar"
    
    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "axis" },
      grid: { top: 30, bottom: 60, left: 60, right: 30 },
      xAxis: { 
        type: "category", 
        data: xData,
        axisLabel: { rotate: xData.length > 10 ? 45 : 0 }
      },
      yAxis: { type: "value" },
      series: [{
        type: chartType.value === "area" ? "line" : chartType.value,
        data: colorizeCategoryData(yData, isBar ? [3, 3, 0, 0] : undefined),
        smooth: true,
        lineStyle: !isBar ? { color: PRIMARY_CHART_COLOR, width: 2 } : undefined,
        areaStyle: chartType.value === "area" ? { color: makeAreaGradient(PRIMARY_CHART_COLOR) } : undefined
      }]
    }
  }
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value) return
  
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  
  const option = buildOption()
  if (option) {
    chartInstance.clear()
    chartInstance.setOption(option)
  }
}

const exportPng = () => {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({ pixelRatio: 2, backgroundColor: "#ffffff" })
  const link = document.createElement("a")
  link.href = url
  link.download = "chart.png"
  link.click()
}

// 监听数据变化
watch(() => props.rows, () => {
  autoDetectFields()
  renderChart()
}, { immediate: true })

watch([chartType, xAxisField, yAxisField, seriesField], () => {
  renderChart()
})

onMounted(() => {
  window.addEventListener("resize", () => chartInstance?.resize())
})
</script>
