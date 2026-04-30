<template>
  <div class="message-chart">
    <div class="chart-header">
      <span class="chart-title">数据可视化（点击图表钻取）</span>
      <div class="chart-actions">
        <el-select v-model="chartType" size="small" style="width: 90px;" placeholder="图表类型">
          <el-option label="折线图" value="line" />
          <el-option label="柱状图" value="bar" />
          <el-option label="饼图" value="pie" />
        </el-select>
        <el-select v-model="sortOrder" size="small" style="width: 80px;">
          <el-option label="默认" value="none" />
          <el-option label="降序" value="desc" />
          <el-option label="升序" value="asc" />
        </el-select>
        <el-button size="small" text @click="showDimensionConfig = !showDimensionConfig">
          <el-icon><Setting /></el-icon>
          维度
        </el-button>
        <el-button v-if="sqlQuery" size="small" type="primary" text @click="showPinDialog = true">
          <el-icon><Star /></el-icon>
          固定
        </el-button>
      </div>
    </div>
    
    <!-- 维度配置面板 -->
    <div v-if="showDimensionConfig" class="dimension-config">
      <div class="dimension-item">
        <span class="dimension-label">X轴:</span>
        <el-select v-model="selectedXField" size="small" placeholder="选择X轴字段">
          <el-option v-for="col in columns" :key="col" :label="col" :value="col" />
        </el-select>
      </div>
      <div class="dimension-item">
        <span class="dimension-label">Y轴:</span>
        <el-select v-model="selectedYField" size="small" placeholder="选择Y轴字段">
          <el-option v-for="col in numericColumns" :key="col" :label="col" :value="col" />
        </el-select>
      </div>
      <div class="dimension-item">
        <span class="dimension-label">分组:</span>
        <el-select v-model="selectedGroupFields" size="small" placeholder="无分组" clearable multiple collapse-tags>
          <el-option v-for="col in groupableColumns" :key="col" :label="col" :value="col" />
        </el-select>
      </div>
    </div>

    <div v-if="selectedRow && (drillLoading || drillActions.length || drillAttempted)" class="drill-bar">
      <div class="drill-bar-title">已选中图表项：{{ selectedSummary }}</div>
      <div v-if="drillLoading" class="drill-loading">正在生成下钻建议...</div>
      <div v-else-if="!drillActions.length" class="drill-empty">当前图表项没有可用的下钻建议</div>
      <div class="drill-actions-bar">
        <el-button
          v-for="action in drillActions"
          :key="action.id"
          size="small"
          type="primary"
          plain
          @click="runDrill(action)"
        >
          {{ action.label }}
        </el-button>
      </div>
    </div>

    <div ref="chartRef" class="chart-body"></div>
    
    <!-- 固定到Dashboard弹窗 -->
    <el-dialog v-model="showPinDialog" title="固定到Dashboard" width="400px">
      <el-form label-width="80px">
        <el-form-item label="图表标题">
          <el-input v-model="pinForm.title" placeholder="请输入图表标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="pinForm.description" type="textarea" :rows="2" placeholder="可选描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPinDialog = false">取消</el-button>
        <el-button type="primary" :loading="pinLoading" @click="pinToDashboard">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from "vue"
import { Star, Setting } from "@element-plus/icons-vue"
import { ElMessage } from "element-plus"
import axios from "axios"
import * as echarts from "echarts"
import { useQueryStore, type ChatMessage, type DrillAction } from "@/store/query"
import { useDatasourceStore } from "@/store/datasource"

const props = defineProps<{
  message: ChatMessage
  columns: string[]
  rows: Array<Record<string, any>>
  sqlQuery?: string
}>()

const chartRef = ref<HTMLDivElement | null>(null)
const queryStore = useQueryStore()
const datasourceStore = useDatasourceStore()
const chartType = ref<"line" | "bar" | "pie">("line")
const sortOrder = ref<"none" | "desc" | "asc">("none")
const showDimensionConfig = ref(false)
let chartInstance: echarts.ECharts | null = null
const selectedRow = ref<Record<string, any> | null>(null)
const drillActions = ref<DrillAction[]>([])
const drillLoading = ref(false)
const drillAttempted = ref(false)

// 用户选择的维度
const selectedXField = ref("")
const selectedYField = ref("")
const selectedGroupFields = ref<string[]>([])

// 固定相关
const showPinDialog = ref(false)
const pinLoading = ref(false)
const pinForm = ref({
  title: "",
  description: ""
})

// 颜色调色板
const colorPalette = [
  "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
  "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc", "#48b8d0"
]

// 识别数值列
const numericColumns = computed(() => {
  if (!props.rows?.length) return []
  return props.columns.filter(col => {
    const val = props.rows[0][col]
    return typeof val === "number" || (!isNaN(Number(val)) && val !== null && val !== "")
  })
})

// 可分组的列（非X轴和非Y轴的字段）
const groupableColumns = computed(() => {
  return props.columns.filter(col => {
    // 排除已选的X轴和Y轴字段
    if (col === selectedXField.value || col === selectedYField.value) return false
    const lower = col.toLowerCase()
    // 包含ID、名称、类型等标识性字段
    return lower.includes("id") || lower.includes("name") || lower.includes("type") || 
           lower.includes("device") || lower.includes("equipment") || lower.includes("alarm") ||
           lower.includes("machine") || lower.includes("category") || lower.includes("code") ||
           lower.includes("error")
  })
})

// 自动识别默认字段并智能配置图表
const autoDetectFields = () => {
  if (!props.rows?.length || !props.columns?.length) return
  
  // 1. 识别时间字段
  const dateFields = ["stat_date", "date", "time", "day", "month", "week", "year", "created_at"]
  const detectedTimeField = props.columns.find(c => dateFields.some(d => c.toLowerCase().includes(d)))
  
  // 2. 识别数值字段（Y轴）
  const valueFields = ["count", "total", "sum", "occurrence", "times", "amount", "num", "qty", "value"]
  const detectedYField = numericColumns.value.find(c => valueFields.some(v => c.toLowerCase().includes(v))) || numericColumns.value[0] || ""
  
  // 3. 识别分组字段
  const groupFieldPatterns = ["equipment_id", "equipmentid", "device_id", "alarm_id", "error_code", "device", "equipment", "alarm", "machine_id", "machine", "category", "type", "name"]
  const detectedGroupFields = props.columns.filter(c => {
    if (c === detectedTimeField || c === detectedYField) return false
    const lower = c.toLowerCase()
    return groupFieldPatterns.some(g => lower.includes(g) || lower === g)
  })
  
  // 4. 确定X轴字段
  let detectedXField: string
  if (detectedTimeField) {
    // 有时间字段，X轴用时间
    detectedXField = detectedTimeField
  } else if (detectedGroupFields.length > 0) {
    // 无时间字段，X轴用第一个分组字段
    detectedXField = detectedGroupFields[0]
  } else {
    // 默认用第一列
    detectedXField = props.columns[0]
  }
  
  // 5. 调整分组字段（排除已用作X轴的）
  const finalGroupFields = detectedGroupFields.filter(f => f !== detectedXField)
  
  // 6. 智能选择图表类型
  const hasTimeAxis = !!detectedTimeField
  const hasMultiGroup = finalGroupFields.length > 0
  const uniqueXValues = new Set(props.rows.map(r => r[detectedXField])).size
  
  if (hasTimeAxis) {
    // 有时间轴 → 折线图（展示趋势）
    chartType.value = "line"
    sortOrder.value = "none"  // 时间序列不排序
  } else if (uniqueXValues <= 6 && !hasMultiGroup) {
    // 少量分类且无多分组 → 饼图
    chartType.value = "pie"
    sortOrder.value = "desc"
  } else {
    // 其他情况 → 柱状图，按数值降序
    chartType.value = "bar"
    sortOrder.value = "desc"
  }
  
  // 7. 设置选择的字段
  selectedXField.value = detectedXField
  selectedYField.value = detectedYField
  selectedGroupFields.value = finalGroupFields
}

// 判断是否为多系列数据
const isMultiSeries = computed(() => {
  return selectedGroupFields.value.length > 0 && selectedXField.value && props.rows.length > 0
})

const selectedSummary = computed(() => {
  if (!selectedRow.value || !selectedXField.value) return ""
  return `${selectedXField.value}: ${selectedRow.value[selectedXField.value]}`
})

// 构建多系列图表配置
const buildMultiSeriesOption = () => {
  if (selectedGroupFields.value.length === 0 || !selectedXField.value || !selectedYField.value) return null
  
  // 生成组合分组键
  const getGroupKey = (row: Record<string, any>) => {
    return selectedGroupFields.value.map(field => String(row[field])).join(" | ")
  }
  
  // 获取所有分组和X轴值
  const groups = [...new Set(props.rows.map(r => getGroupKey(r)))]
  let xValues = [...new Set(props.rows.map(r => String(r[selectedXField.value])))]
  
  // 对X轴排序
  xValues.sort()
  
  // 构建数据Map
  const dataMap = new Map<string, Map<string, number>>()
  props.rows.forEach(row => {
    const group = getGroupKey(row)
    const x = String(row[selectedXField.value])
    const value = Number(row[selectedYField.value]) || 0
    
    if (!dataMap.has(group)) dataMap.set(group, new Map())
    // 如果同一组合有多个值，累加
    const existing = dataMap.get(group)!.get(x) || 0
    dataMap.get(group)!.set(x, existing + value)
  })
  
  // 构建系列
  const series = groups.map((group, idx) => {
    const groupData = dataMap.get(group)!
    return {
      name: group,
      type: chartType.value,
      data: xValues.map(x => groupData.get(x) || 0),
      smooth: chartType.value === "line",
      itemStyle: { color: colorPalette[idx % colorPalette.length] }
    }
  })
  
  return {
    tooltip: { 
      trigger: "axis",
      axisPointer: { type: "cross" }
    },
    legend: {
      type: "scroll",
      top: 0,
      data: groups
    },
    grid: { top: 40, bottom: 60, left: 60, right: 20 },
    xAxis: { 
      type: "category", 
      data: xValues,
      axisLabel: { rotate: xValues.length > 8 ? 45 : 0, fontSize: 11 }
    },
    yAxis: { type: "value" },
    series
  }
}

// 构建单系列图表配置
const buildSingleSeriesOption = () => {
  const xField = selectedXField.value
  const yField = selectedYField.value
  if (!xField || !yField || !props.rows?.length) return null

  // 饼图
  if (chartType.value === "pie") {
    let data = props.rows.map(row => ({
      name: String(row[xField]),
      value: Number(row[yField]) || 0
    }))
    if (sortOrder.value === "desc") data.sort((a, b) => b.value - a.value)
    else if (sortOrder.value === "asc") data.sort((a, b) => a.value - b.value)
    
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
  let dataPoints = props.rows.map(r => ({
    x: String(r[xField]),
    y: Number(r[yField]) || 0
  }))
  
  if (sortOrder.value === "desc") dataPoints.sort((a, b) => b.y - a.y)
  else if (sortOrder.value === "asc") dataPoints.sort((a, b) => a.y - b.y)
  
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
      type: chartType.value,
      data: dataPoints.map(d => d.y),
      smooth: chartType.value === "line",
      itemStyle: { color: "#0f766e" }
    }]
  }
}

// 构建图表配置
const buildOption = () => {
  // 多系列数据使用多系列配置
  if (isMultiSeries.value && chartType.value !== "pie") {
    return buildMultiSeriesOption()
  }
  return buildSingleSeriesOption()
}

const getGroupKey = (row: Record<string, any>) => {
  return selectedGroupFields.value.map(field => String(row[field])).join(" | ")
}

const findRowFromChartSelection = (params: any) => {
  if (!selectedXField.value) return null

  if (chartType.value === "pie") {
    return props.rows.find(row => String(row[selectedXField.value]) === String(params.name)) || null
  }

  const selectedName = String(params.name)
  if (isMultiSeries.value && selectedGroupFields.value.length > 0) {
    const selectedSeries = String(params.seriesName || "")
    return props.rows.find((row) => {
      return String(row[selectedXField.value]) === selectedName && getGroupKey(row) === selectedSeries
    }) || null
  }

  return props.rows.find(row => String(row[selectedXField.value]) === selectedName) || null
}

const handleChartClick = async (params: any) => {
  const row = findRowFromChartSelection(params)
  if (!row) return
  selectedRow.value = row
  drillAttempted.value = true
  drillLoading.value = true
  try {
    if (!props.sqlQuery || !props.message.sourceQuestion || !selectedXField.value) {
      drillActions.value = []
      return
    }
    const preview = await queryStore.getDrillActions(
      props.message.sourceQuestion,
      props.sqlQuery,
      selectedXField.value,
      props.columns,
      row
    )
    drillActions.value = preview.actions
  } catch {
    drillActions.value = []
    ElMessage.error("加载钻取动作失败")
  } finally {
    drillLoading.value = false
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
    chartInstance.off("click")
    chartInstance.on("click", handleChartClick)
  }
}

const runDrill = async (action: DrillAction) => {
  await queryStore.ask(action.question, "text2sql", {
    pathLabel: action.label,
    sourceLabel: action.source_dimension_label,
    sourceValue: action.source_value,
    targetLabel: action.target_dimension_label,
    parentQuestion: props.message.sourceQuestion || props.message.content,
    parentContext: props.message.drillContext,
  }, props.message.historyId)
}

// 固定到Dashboard
const pinToDashboard = async () => {
  if (!pinForm.value.title.trim()) {
    ElMessage.warning("请输入图表标题")
    return
  }
  if (!props.sqlQuery) {
    ElMessage.error("缺少SQL查询语句")
    return
  }
  
  pinLoading.value = true
  try {
    await axios.post("/api/pinned-charts", {
      title: pinForm.value.title.trim(),
      description: pinForm.value.description.trim() || null,
      sql_query: props.sqlQuery,
      chart_type: chartType.value,
      sort_order: sortOrder.value,
      datasource_id: datasourceStore.currentId,
    })
    ElMessage.success("已固定到Dashboard")
    showPinDialog.value = false
    pinForm.value = { title: "", description: "" }
  } catch (error) {
    ElMessage.error("固定失败，请重试")
  } finally {
    pinLoading.value = false
  }
}

watch([chartType, sortOrder, selectedXField, selectedYField, selectedGroupFields], () => {
  selectedRow.value = null
  drillActions.value = []
  drillLoading.value = false
  drillAttempted.value = false
  renderChart()
}, { deep: true })
watch(() => props.rows, () => {
  selectedRow.value = null
  drillActions.value = []
  drillLoading.value = false
  drillAttempted.value = false
  autoDetectFields()
  renderChart()
}, { deep: true, immediate: true })

onMounted(() => {
  autoDetectFields()
  renderChart()
  window.addEventListener("resize", () => chartInstance?.resize())
})
</script>

<style scoped>
.message-chart {
  width: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}

.chart-title {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.chart-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.dimension-config {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dimension-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.dimension-item .el-select {
  width: 160px;
}

.dimension-item:last-child .el-select {
  width: 220px;
}

.chart-body {
  width: 100%;
  height: 280px;
}

.drill-bar {
  padding: 10px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #f8fafc;
}

.drill-loading {
  margin-top: 8px;
  font-size: 13px;
  color: #606266;
}

.drill-empty {
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

.drill-bar-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.drill-actions-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-action-bar {
  margin-bottom: 8px;
}
</style>
