import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("trusted metrics alerts and scheduled reports live under BI analysis menu", () => {
  const layout = read("src/layouts/MainLayout.vue")

  const biAnalysisBlock = layout.match(/key:\s*"bi-assets"[\s\S]*?key:\s*"system-admin"/)?.[0] || ""
  assert.match(biAnalysisBlock, /path:\s*"\/dashboard-center",\s*label:\s*"看板中心"/)
  assert.match(biAnalysisBlock, /path:\s*"\/metric-settings",\s*label:\s*"可信指标"/)
  assert.match(biAnalysisBlock, /path:\s*"\/alert-settings",\s*label:\s*"预警管理"/)
  assert.match(biAnalysisBlock, /path:\s*"\/scheduled-reports",\s*label:\s*"定时报告"/)
  assert.doesNotMatch(layout, /key:\s*"data-governance"/)
})

test("metric creation uses a system-user tree selector for certifier", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /<el-tree-select/)
  assert.match(view, /\/api\/metrics\/certifiers/)
  assert.match(view, /certifierTreeData/)
  assert.match(view, /certified_by:\s*form\.value\.certified_by/)
  assert.match(view, /请选择认证人/)
})

test("metric creation binds trusted metrics to datasets only", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /\/api\/datasets/)
  assert.match(view, /v-model="form\.dataset_id"/)
  assert.match(view, /请选择数据集/)
  assert.match(view, /dataset_id:\s*form\.value\.dataset_id/)
  assert.doesNotMatch(view, /v-model="form\.datasource_id"/)
  assert.doesNotMatch(view, /datasource_id:\s*form\.value\.datasource_id/)
})
