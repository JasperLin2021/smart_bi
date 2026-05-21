import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("smart query chart modal matches dashboard chart creator flow and targets a dashboard", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /加入看板/)
  assert.match(component, /el-tabs v-model="pinDialogTab"/)
  assert.match(component, /图表配置/)
  assert.match(component, /数据查询/)
  assert.match(component, /预览/)
  assert.match(component, /目标看板/)
  assert.match(component, /\/api\/dashboards/)
  assert.match(component, /\/api\/pinned-charts\/add-to-dashboard/)
})

test("smart query chart pin form is prefilled from the current query chart", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /pinChartForm\.sql_query = props\.sqlQuery/)
  assert.match(component, /pinChartForm\.question = props\.message\.sourceQuestion/)
  assert.match(component, /pinChartForm\.chart_type = chartType\.value/)
  assert.match(component, /pinPreviewResult\.value = \{ columns: props\.columns, rows: props\.rows \}/)
})

test("smart query add-to-dashboard dialog stretches description above footer actions", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /class="chart-creator-dialog pin-chart-creator-dialog"/)
  assert.match(component, /body-class="pin-chart-dialog-body"/)
  assert.match(component, /footer-class="pin-chart-dialog-footer"/)
  assert.match(component, /class="modal-tab-content config-tab-content"/)
  assert.match(component, /class="pin-description-field"/)
  assert.match(component, /class="pin-description-input"/)
  assert.match(component, /:global\(\.el-dialog\.pin-chart-creator-dialog\)[\s\S]*height: min\(760px, calc\(100vh - 12vh\)\)/)
  assert.match(component, /:global\(\.pin-chart-dialog-body\)[\s\S]*flex: 1 1 auto/)
  assert.match(component, /\.chart-creator-form[\s\S]*height: 100%/)
  assert.match(component, /\.modal-tabs[\s\S]*flex: 1 1 auto/)
  assert.match(component, /\.config-tab-content[\s\S]*flex: 1 1 auto/)
  assert.match(component, /\.pin-description-field[\s\S]*flex: 1 1 auto/)
  assert.match(component, /\.pin-description-input :deep\(\.el-textarea__inner\)[\s\S]*height: 100%/)
})

test("message chart can render agentic chart specs with facet tabs", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /tabs_by_field/)
  assert.match(component, /selectedFacet/)
  assert.match(component, /chartRows/)
  assert.match(component, /facetValues/)
  assert.match(component, /layout === "tabs_by_field"/)
  assert.match(component, /selectedGroupFields\.value = validSeriesFields/)
})

test("message chart replaces high-cardinality facet tabs with top n explorer", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /const FACET_TAB_LIMIT = 8/)
  assert.match(component, /const HIGH_CARDINALITY_FACET_TOP_N = 10/)
  assert.match(component, /showHighCardinalityFacetExplorer/)
  assert.match(component, /facetViewMode/)
  assert.match(component, /selectedFacetValues/)
  assert.match(component, /class="facet-explorer"/)
  assert.match(component, /<el-segmented[\s\S]*v-model="facetViewMode"/)
  assert.match(component, /filterable[\s\S]*multiple[\s\S]*collapse-tags/)
  assert.match(component, /OTHER_FACET_BUCKET_LABEL = "其他"/)
  assert.match(component, /facetValues\.value\.length <= FACET_TAB_LIMIT/)
  assert.match(component, /activeGroupFields/)
})

test("message chart resizes after chat bubble layout settles", () => {
  const component = read("src/components/MessageChart.vue")

  assert.match(component, /onBeforeUnmount/)
  assert.match(component, /let chartResizeObserver: ResizeObserver \| null = null/)
  assert.match(component, /const resizeChart = \(\) => \{[\s\S]*requestAnimationFrame/)
  assert.match(component, /chartResizeObserver = new ResizeObserver\(resizeChart\)/)
  assert.match(component, /chartResizeObserver\.observe\(chartRef\.value\)/)
  assert.match(component, /window\.addEventListener\("resize", resizeChart\)/)
  assert.match(component, /window\.removeEventListener\("resize", resizeChart\)/)
  assert.match(component, /chartInstance\?\.dispose\(\)/)
})

test("drill suggestions show loading affordance before actions are clickable", () => {
  const chart = read("src/components/MessageChart.vue")
  const table = read("src/components/MessageTable.vue")

  assert.match(chart, /v-if="selectedRow && \(drillLoading \|\| drillActions\.length \|\| drillAttempted\)"/)
  assert.match(chart, /class="drill-action-loading"/)
  assert.match(chart, /:loading="drillLoading"/)
  assert.match(chart, /下钻建议生成中/)
  assert.match(chart, /let drillRequestId = 0/)
  assert.match(chart, /const requestId = \+\+drillRequestId/)
  assert.match(chart, /if \(requestId !== drillRequestId\) return/)

  assert.match(table, /const drillLoading = ref\(false\)/)
  assert.match(table, /const drillAttempted = ref\(false\)/)
  assert.match(table, /v-if="selectedRow && \(drillLoading \|\| drillActions\.length \|\| drillAttempted\)"/)
  assert.match(table, /class="drill-action-loading"/)
  assert.match(table, /:loading="drillLoading"/)
  assert.match(table, /下钻建议生成中/)
  assert.match(table, /let drillRequestId = 0/)
  assert.match(table, /const requestId = \+\+drillRequestId/)
  assert.match(table, /if \(requestId !== drillRequestId\) return/)
})
