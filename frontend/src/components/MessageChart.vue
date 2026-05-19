<template>
  <div class="message-chart">
    <div class="chart-header">
      <div class="chart-title-wrap">
        <span class="chart-title">数据可视化（点击图表钻取）</span>
        <div v-if="message.trustSignals?.length" class="chart-trust-tags">
          <el-tag
            v-for="signal in message.trustSignals"
            :key="signal.metric_id"
            size="small"
            :type="certificationTagType(signal.certification_status)"
            effect="plain"
          >
            {{ signal.metric_name }} · {{ certificationLabel(signal.certification_status) }}
          </el-tag>
        </div>
      </div>
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
        <el-button v-if="sqlQuery" size="small" type="primary" text @click="openPinDialog">
          <el-icon><Star /></el-icon>
          加入看板
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

    <el-tabs
      v-if="showFacetTabs"
      v-model="selectedFacet"
      class="chart-facet-tabs"
    >
      <el-tab-pane
        v-for="value in facetValues"
        :key="value"
        :label="value"
        :name="value"
      />
    </el-tabs>

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
    
    <el-dialog
      v-model="showPinDialog"
      title="加入看板"
      width="860px"
      top="6vh"
      append-to-body
      class="chart-creator-dialog pin-chart-creator-dialog"
      body-class="pin-chart-dialog-body"
      footer-class="pin-chart-dialog-footer"
      @opened="dispatchResize"
    >
      <el-form :model="pinChartForm" label-position="top" class="chart-creator-form">
        <el-tabs v-model="pinDialogTab" class="modal-tabs">
          <el-tab-pane label="图表配置" name="config">
            <div class="modal-tab-content config-tab-content">
              <el-row :gutter="12">
                <el-col :xs="24" :sm="12">
                  <el-form-item label="标题">
                    <el-input v-model="pinChartForm.title" maxlength="128" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="目标看板">
                    <el-select
                      v-model="pinChartForm.dashboard_id"
                      :loading="dashboardsLoading"
                      :disabled="dashboards.length === 0"
                      filterable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="dashboard in dashboards"
                        :key="dashboard.id"
                        :label="dashboard.title"
                        :value="dashboard.id"
                      >
                        <div class="dashboard-option">
                          <strong>{{ dashboard.title }}</strong>
                          <small>{{ dashboardComponentCount(dashboard) }} 个组件</small>
                        </div>
                      </el-option>
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="数据源">
                    <el-select v-model="pinChartForm.datasource_id" style="width: 100%">
                      <el-option
                        v-for="datasource in datasourceStore.datasources"
                        :key="datasource.id"
                        :label="datasource.name"
                        :value="datasource.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="图表类型">
                    <el-select v-model="pinChartForm.chart_type" style="width: 100%">
                      <el-option
                        v-for="option in chartTypeOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="排序">
                    <el-select v-model="pinChartForm.sort_order" style="width: 100%">
                      <el-option label="默认" value="none" />
                      <el-option label="降序" value="desc" />
                      <el-option label="升序" value="asc" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="描述" class="pin-description-field">
                <el-input
                  v-model="pinChartForm.description"
                  class="pin-description-input"
                  type="textarea"
                  :rows="8"
                  resize="vertical"
                />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="数据查询" name="query">
            <div class="modal-tab-content">
              <el-form-item label="创建方式">
                <el-segmented v-model="pinCreateMode" :options="chartCreateModeOptions" />
              </el-form-item>
              <el-form-item v-if="pinCreateMode === 'nl'" label="问题">
                <el-input
                  v-model="pinChartForm.question"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：统计每个月的销售额趋势"
                />
              </el-form-item>
              <el-form-item label="SQL">
                <el-input v-model="pinChartForm.sql_query" type="textarea" :rows="6" placeholder="SELECT ..." />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="预览" name="preview">
            <div class="modal-tab-content">
              <section class="chart-preview-panel">
                <PinnedChartCard
                  v-if="pinPreviewResult && pinPreviewResult.rows.length"
                  :chart="pinPreviewCard"
                  @delete="noop"
                />
                <el-empty v-else description="点击底部「预览」按钮生成图表" :image-size="72" />
              </section>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="showPinDialog = false">取消</el-button>
        <el-button :loading="pinPreviewLoading" @click="previewPinChartDraft">预览</el-button>
        <el-button type="primary" :loading="pinLoading" @click="savePinChartToDashboard">
          保存并加入看板
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, nextTick } from "vue"
import { Star, Setting } from "@element-plus/icons-vue"
import { ElMessage } from "element-plus"
import axios from "axios"
import * as echarts from "echarts"
import { useQueryStore, type ChartSpec, type ChatMessage, type DrillAction } from "@/store/query"
import { useDatasourceStore } from "@/store/datasource"
import PinnedChartCard from "@/components/PinnedChartCard.vue"
import {
  CHART_COLOR_PALETTE,
  PRIMARY_CHART_COLOR,
  chartColorAt,
  colorizeCategoryData,
} from "@/utils/chartColors"

const props = defineProps<{
  message: ChatMessage
  columns: string[]
  rows: Array<Record<string, any>>
  sqlQuery?: string
  chartSpec?: ChartSpec | null
}>()

interface DashboardOption {
  id: number
  title: string
  layout_json: { components?: Array<Record<string, unknown>> } | null
}

interface ChartPreviewResult {
  columns: string[]
  rows: Array<Record<string, unknown>>
}

interface PinnedChartPreviewCard {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, unknown>>
}

const chartRef = ref<HTMLDivElement | null>(null)
const queryStore = useQueryStore()
const datasourceStore = useDatasourceStore()
const dispatchResize = () => globalThis.dispatchEvent(new Event("resize"))
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
const selectedFacet = ref("")

// 固定相关
const showPinDialog = ref(false)
const pinLoading = ref(false)
const pinPreviewLoading = ref(false)
const dashboardsLoading = ref(false)
const dashboards = ref<DashboardOption[]>([])
const pinDialogTab = ref("config")
const pinCreateMode = ref("sql")
const pinPreviewResult = ref<ChartPreviewResult | null>(null)
const pinChartForm = reactive({
  dashboard_id: null as number | null,
  title: "",
  description: "",
  question: "",
  sql_query: "",
  datasource_id: null as number | null,
  chart_type: "bar",
  sort_order: "desc",
})

const chartCreateModeOptions = [
  { label: "自然语言", value: "nl" },
  { label: "SQL", value: "sql" },
]

const chartTypeOptions = [
  { label: "指标卡", value: "kpi" },
  { label: "明细表", value: "table" },
  { label: "柱状图", value: "bar" },
  { label: "条形图", value: "horizontal_bar" },
  { label: "折线图", value: "line" },
  { label: "面积图", value: "area" },
  { label: "饼图", value: "pie" },
  { label: "环形图", value: "donut" },
  { label: "散点图", value: "scatter" },
  { label: "组合图", value: "combo" },
]

// 识别数值列
const numericColumns = computed(() => {
  if (!props.rows?.length) return []
  return props.columns.filter(col => {
    const val = props.rows[0][col]
    return typeof val === "number" || (!isNaN(Number(val)) && val !== null && val !== "")
  })
})

const normalizeChartType = (value?: string | null): "line" | "bar" | "pie" => {
  if (value === "bar" || value === "horizontal_bar") return "bar"
  if (value === "pie" || value === "donut") return "pie"
  return "line"
}

const normalizeSortOrder = (value?: string | null): "none" | "desc" | "asc" => {
  if (value === "desc" || value === "asc") return value
  return "none"
}

const resolveColumn = (value?: string | null) => {
  if (!value) return ""
  return props.columns.find(col => col === value || col.toLowerCase() === value.toLowerCase()) || ""
}

const facetField = computed(() => {
  const spec = props.chartSpec
  if (!spec || spec.layout !== "tabs_by_field") return ""
  return resolveColumn(spec.facet_field)
})

const facetValues = computed(() => {
  if (!facetField.value) return []
  return [...new Set(props.rows.map(row => String(row[facetField.value] ?? "")).filter(Boolean))]
})

const showFacetTabs = computed(() => facetField.value && facetValues.value.length > 1)

const chartRows = computed(() => {
  if (!showFacetTabs.value || !selectedFacet.value || !facetField.value) return props.rows
  return props.rows.filter(row => String(row[facetField.value]) === selectedFacet.value)
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

const applyChartSpec = () => {
  const spec = props.chartSpec
  if (!spec || !props.columns.length) return false

  const xField = resolveColumn(spec.x_field)
  const yField = resolveColumn(spec.y_field)
  const rawSeriesFields = Array.isArray(spec.series_fields) ? spec.series_fields : []
  const validSeriesFields = rawSeriesFields
    .map(field => resolveColumn(field))
    .filter((field): field is string => Boolean(field) && field !== xField && field !== yField && field !== facetField.value)

  chartType.value = normalizeChartType(spec.chart_type)
  sortOrder.value = normalizeSortOrder(spec.sort_order)
  if (xField) selectedXField.value = xField
  if (yField) selectedYField.value = yField
  selectedGroupFields.value = validSeriesFields

  if (spec.layout === "tabs_by_field" && facetValues.value.length > 0 && !facetValues.value.includes(selectedFacet.value)) {
    selectedFacet.value = facetValues.value[0]
  }
  return Boolean(xField && yField)
}

const configureChartFields = () => {
  if (!applyChartSpec()) {
    autoDetectFields()
  }
  if (facetValues.value.length > 0 && !facetValues.value.includes(selectedFacet.value)) {
    selectedFacet.value = facetValues.value[0]
  }
}

// 判断是否为多系列数据
const isMultiSeries = computed(() => {
  return selectedGroupFields.value.length > 0 && selectedXField.value && chartRows.value.length > 0
})

const selectedSummary = computed(() => {
  if (!selectedRow.value || !selectedXField.value) return ""
  return `${selectedXField.value}: ${selectedRow.value[selectedXField.value]}`
})

const effectiveDatasourceId = computed(() =>
  queryStore.selectedDatasourceId || datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
)

const pinPreviewCard = computed<PinnedChartPreviewCard>(() => ({
  id: 0,
  title: pinChartForm.title || "预览图表",
  description: pinChartForm.description || null,
  chart_type: pinChartForm.chart_type,
  sort_order: pinChartForm.sort_order,
  columns: pinPreviewResult.value?.columns || props.columns,
  rows: pinPreviewResult.value?.rows || props.rows,
}))

const certificationLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审核",
    certified: "已认证",
    deprecated: "已废弃",
  }
  return labels[status] || status
}

const certificationTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    draft: "info",
    pending_review: "warning",
    certified: "success",
    deprecated: "danger",
  }
  return types[status] || "info"
}

// 构建多系列图表配置
const buildMultiSeriesOption = () => {
  if (selectedGroupFields.value.length === 0 || !selectedXField.value || !selectedYField.value) return null
  
  // 生成组合分组键
  const getGroupKey = (row: Record<string, any>) => {
    return selectedGroupFields.value.map(field => String(row[field])).join(" | ")
  }
  
  // 获取所有分组和X轴值
  const rows = chartRows.value
  const groups = [...new Set(rows.map(r => getGroupKey(r)))]
  let xValues = [...new Set(rows.map(r => String(r[selectedXField.value])))]
  
  // 对X轴排序
  xValues.sort()
  
  // 构建数据Map
  const dataMap = new Map<string, Map<string, number>>()
  rows.forEach(row => {
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
    const color = chartColorAt(idx)
    return {
      name: group,
      type: chartType.value,
      data: xValues.map(x => groupData.get(x) || 0),
      smooth: chartType.value === "line",
      itemStyle: { color },
      lineStyle: chartType.value === "line" ? { color, width: 2 } : undefined,
    }
  })
  
  return {
    color: CHART_COLOR_PALETTE,
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
  const rows = chartRows.value
  if (!xField || !yField || !rows.length) return null

  // 饼图
  if (chartType.value === "pie") {
    let data = rows.map(row => ({
      name: String(row[xField]),
      value: Number(row[yField]) || 0
    }))
    if (sortOrder.value === "desc") data.sort((a, b) => b.value - a.value)
    else if (sortOrder.value === "asc") data.sort((a, b) => a.value - b.value)
    
    return {
      color: CHART_COLOR_PALETTE,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        type: "pie",
        radius: ["30%", "60%"],
        data: data.slice(0, 15),
        itemStyle: { borderRadius: 4, borderWidth: 1, borderColor: "#fff" },
      }]
    }
  }

  // 柱状图/折线图
  let dataPoints = rows.map(r => ({
    x: String(r[xField]),
    y: Number(r[yField]) || 0
  }))
  
  if (sortOrder.value === "desc") dataPoints.sort((a, b) => b.y - a.y)
  else if (sortOrder.value === "asc") dataPoints.sort((a, b) => a.y - b.y)
  
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
      type: chartType.value,
      data: colorizeCategoryData(dataPoints.map(d => d.y), chartType.value === "bar" ? [3, 3, 0, 0] : undefined),
      smooth: chartType.value === "line",
      lineStyle: chartType.value === "line" ? { color: PRIMARY_CHART_COLOR, width: 2 } : undefined,
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
    return chartRows.value.find(row => String(row[selectedXField.value]) === String(params.name)) || null
  }

  const selectedName = String(params.name)
  if (isMultiSeries.value && selectedGroupFields.value.length > 0) {
    const selectedSeries = String(params.seriesName || "")
    return chartRows.value.find((row) => {
      return String(row[selectedXField.value]) === selectedName && getGroupKey(row) === selectedSeries
    }) || null
  }

  return chartRows.value.find(row => String(row[selectedXField.value]) === selectedName) || null
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
    chartInstance.on("click", (params) => {
      void handleChartClick(params)
    })
  }
}

const runDrill = async (action: DrillAction) => {
  await queryStore.ask(action.question, props.message.mode || "business", {
    pathLabel: action.label,
    sourceLabel: action.source_dimension_label,
    sourceValue: action.source_value,
    targetLabel: action.target_dimension_label,
    parentQuestion: props.message.sourceQuestion || props.message.content,
    parentContext: props.message.drillContext,
  }, props.message.historyId)
}

const dashboardComponentCount = (dashboard: DashboardOption) => dashboard.layout_json?.components?.length || 0

const noop = () => {}

const fetchDashboards = async () => {
  dashboardsLoading.value = true
  try {
    const response = await axios.get("/api/dashboards")
    dashboards.value = response.data.items || []
    if (!pinChartForm.dashboard_id && dashboards.value.length > 0) {
      pinChartForm.dashboard_id = dashboards.value[0].id
    }
  } catch {
    dashboards.value = []
    ElMessage.error("看板列表加载失败")
  } finally {
    dashboardsLoading.value = false
  }
}

const prefillPinChartForm = () => {
  pinChartForm.dashboard_id = dashboards.value[0]?.id || null
  pinChartForm.title = (props.message.sourceQuestion || props.message.content || "智能问数图表").slice(0, 128)
  pinChartForm.description = props.message.summary || ""
  pinChartForm.question = props.message.sourceQuestion || ""
  pinChartForm.sql_query = props.sqlQuery || ""
  pinChartForm.datasource_id = effectiveDatasourceId.value
  pinChartForm.chart_type = chartType.value
  pinChartForm.sort_order = sortOrder.value
  pinPreviewResult.value = { columns: props.columns, rows: props.rows }
}

const openPinDialog = async () => {
  pinDialogTab.value = "config"
  pinCreateMode.value = "sql"
  prefillPinChartForm()
  showPinDialog.value = true
  try {
    if (!datasourceStore.datasources.length) {
      await datasourceStore.fetchDatasources()
      pinChartForm.datasource_id = pinChartForm.datasource_id || effectiveDatasourceId.value
    }
    await fetchDashboards()
  } catch {
    return
  }
}

const previewPinChartDraft = async () => {
  if (pinCreateMode.value === "nl") {
    const question = pinChartForm.question.trim()
    if (!question) {
      ElMessage.warning("请输入问题")
      return false
    }
  } else if (!pinChartForm.sql_query.trim()) {
    ElMessage.warning("请输入 SQL")
    return false
  }

  pinPreviewLoading.value = true
  try {
    if (pinCreateMode.value === "nl") {
      const response = await axios.post("/api/query/ask", {
        question: pinChartForm.question.trim(),
        mode: queryStore.mode,
        datasource_id: pinChartForm.datasource_id,
        dataset_id: queryStore.mode === "business" || queryStore.scopeMode === "dataset" ? queryStore.selectedDatasetId : null,
      })
      pinChartForm.sql_query = response.data.sql_query || ""
      pinPreviewResult.value = response.data.result || { columns: [], rows: [] }
      if (!pinChartForm.title.trim()) {
        pinChartForm.title = pinChartForm.question.trim().slice(0, 128)
      }
    } else {
      const response = await axios.post("/api/pinned-charts/preview", {
        sql_query: pinChartForm.sql_query.trim(),
        datasource_id: pinChartForm.datasource_id,
      })
      pinPreviewResult.value = response.data
    }
    pinDialogTab.value = "preview"
    if (pinPreviewResult.value && !pinPreviewResult.value.rows.length) {
      ElMessage.warning("查询成功，但没有返回数据")
    }
    return true
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "图表预览失败")
    return false
  } finally {
    pinPreviewLoading.value = false
  }
}

const savePinChartToDashboard = async () => {
  if (!pinChartForm.dashboard_id) {
    ElMessage.warning("请选择目标看板")
    return
  }
  if (!pinChartForm.title.trim()) {
    ElMessage.warning("请输入图表标题")
    return
  }
  if (!pinChartForm.sql_query.trim()) {
    ElMessage.error("缺少SQL查询语句")
    return
  }
  
  pinLoading.value = true
  try {
    await axios.post("/api/pinned-charts/add-to-dashboard", {
      dashboard_id: pinChartForm.dashboard_id,
      title: pinChartForm.title.trim(),
      description: pinChartForm.description.trim() || null,
      sql_query: pinChartForm.sql_query.trim(),
      chart_type: pinChartForm.chart_type,
      sort_order: pinChartForm.sort_order,
      datasource_id: pinChartForm.datasource_id,
    })
    const dashboard = dashboards.value.find((item) => item.id === pinChartForm.dashboard_id)
    ElMessage.success(`已加入「${dashboard?.title || "目标"}」看板`)
    showPinDialog.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "加入看板失败，请重试")
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
  configureChartFields()
  renderChart()
}, { deep: true, immediate: true })
watch(() => props.chartSpec, () => {
  selectedRow.value = null
  drillActions.value = []
  drillLoading.value = false
  drillAttempted.value = false
  configureChartFields()
  renderChart()
}, { deep: true })
watch(facetValues, () => {
  if (facetValues.value.length > 0 && !facetValues.value.includes(selectedFacet.value)) {
    selectedFacet.value = facetValues.value[0]
  }
})
watch(selectedFacet, () => {
  selectedRow.value = null
  drillActions.value = []
  drillLoading.value = false
  drillAttempted.value = false
  renderChart()
})

onMounted(() => {
  configureChartFields()
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
  align-items: flex-start;
  gap: 12px;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}

.chart-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.chart-title {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.chart-trust-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chart-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.dimension-config {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.chart-facet-tabs {
  padding: 0 12px;
  background: #ffffff;
  border-bottom: 1px solid #e4e7ed;
}

.chart-facet-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.chart-facet-tabs :deep(.el-tabs__item) {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

:global(.el-dialog.pin-chart-creator-dialog) {
  display: flex;
  flex-direction: column;
  height: min(760px, calc(100vh - 12vh));
  max-height: calc(100vh - 12vh);
  max-width: calc(100vw - 32px);
  margin-top: 6vh !important;
}

:global(.pin-chart-dialog-body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

:global(.pin-chart-dialog-footer) {
  flex: 0 0 auto;
}

.chart-creator-form {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.modal-tabs {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
}

.modal-tabs :deep(.el-tabs__header) {
  flex: 0 0 auto;
  margin-bottom: 0;
}

.modal-tabs :deep(.el-tabs__content) {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.modal-tabs :deep(.el-tab-pane) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.modal-tab-content {
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 18px 4px 4px;
}

.config-tab-content {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: hidden;
}

.config-tab-content :deep(.el-row) {
  flex: 0 0 auto;
}

.pin-description-field {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  margin-bottom: 0;
}

.pin-description-field :deep(.el-form-item__content) {
  flex: 1 1 auto;
  min-height: 0;
}

.pin-description-input {
  width: 100%;
  height: 100%;
}

.pin-description-input :deep(.el-textarea__inner) {
  height: 100%;
  min-height: 220px;
  line-height: 1.55;
}

.dashboard-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-option strong,
.dashboard-option small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dashboard-option small {
  color: #909399;
  flex-shrink: 0;
}

.chart-preview-panel {
  min-height: 320px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}
</style>
