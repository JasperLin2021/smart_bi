<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-header-title">{{ title }}</span>
        <div class="card-header-actions">
          <el-button size="small" @click="exportPng">导出 PNG</el-button>
          <el-button size="small" @click="exportPdf">导出 PDF</el-button>
          <el-select v-model="currentType" size="small" class="field-compact">
            <el-option label="折线图" value="line" />
            <el-option label="柱状图" value="bar" />
            <el-option label="饼图" value="pie" />
            <el-option label="散点图" value="scatter" />
            <el-option label="热力图" value="heatmap" />
          </el-select>
        </div>
      </div>
    </template>
    <div ref="chartRef" class="chart-panel"></div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue"
import * as echarts from "echarts"
import jsPDF from "jspdf"

const props = defineProps<{
  title: string
  categories: string[]
  values: number[]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
const currentType = ref<"line" | "bar" | "pie" | "scatter" | "heatmap">("line")
let chartInstance: echarts.ECharts | null = null

const buildOption = () => {
  if (currentType.value === "pie") {
    return {
      tooltip: { trigger: "item" },
      series: [
        {
          type: "pie",
          radius: "55%",
          data: props.categories.map((name, index) => ({
            name,
            value: props.values[index]
          }))
        }
      ]
    }
  }

  if (currentType.value === "heatmap") {
    return {
      tooltip: { position: "top" },
      grid: { height: "60%", top: "10%" },
      xAxis: { type: "category", data: props.categories },
      yAxis: { type: "category", data: ["指标"] },
      visualMap: { min: 0, max: Math.max(...props.values, 1), calculable: true },
      series: [
        {
          type: "heatmap",
          data: props.values.map((value, index) => [index, 0, value]),
          label: { show: true }
        }
      ]
    }
  }

  return {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: props.categories },
    yAxis: { type: "value" },
    series: [
      {
        type: currentType.value,
        data: props.values
      }
    ]
  }
}

const renderChart = () => {
  if (!chartRef.value) {
    return
  }
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(buildOption())
}

const exportPng = () => {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({ pixelRatio: 2, backgroundColor: "#ffffff" })
  const link = document.createElement("a")
  link.href = url
  link.download = `${props.title}.png`
  link.click()
}

const exportPdf = () => {
  if (!chartInstance) return
  const url = chartInstance.getDataURL({ pixelRatio: 2, backgroundColor: "#ffffff" })
  const pdf = new jsPDF("l", "pt", "a4")
  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  pdf.addImage(url, "PNG", 0, 0, pageWidth, pageHeight)
  pdf.save(`${props.title}.pdf`)
}

onMounted(() => {
  renderChart()
})

watch([currentType, () => props.values], () => {
  renderChart()
})
</script>
