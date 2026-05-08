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
