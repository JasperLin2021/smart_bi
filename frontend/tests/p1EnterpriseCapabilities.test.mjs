import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("P1 enterprise capability routes are registered", () => {
  const router = read("src/router/index.ts")

  assert.match(router, /path:\s*"\/report-center"/)
  assert.match(router, /import\("@\/views\/ReportCenter\.vue"\)/)
  assert.match(router, /path:\s*"\/report-designer\/:id"/)
  assert.match(router, /import\("@\/views\/ReportDesigner\.vue"\)/)
  assert.match(router, /path:\s*"\/data-pipelines"/)
  assert.match(router, /import\("@\/views\/DataPipelines\.vue"\)/)
  assert.match(router, /path:\s*"\/analysis-workbench"/)
  assert.match(router, /import\("@\/views\/AnalysisWorkbench\.vue"\)/)
})

test("P1 enterprise capabilities are visible in the expected sidebar groups", () => {
  const layout = read("src/layouts/MainLayout.vue")
  const workspaceBlock = layout.match(/key:\s*"workspace"[\s\S]*?key:\s*"data-access"/)?.[0] || ""
  const dataAccessBlock = layout.match(/key:\s*"data-access"[\s\S]*?key:\s*"bi-assets"/)?.[0] || ""
  const biAnalysisBlock = layout.match(/key:\s*"bi-assets"[\s\S]*?key:\s*"system-admin"/)?.[0] || ""

  assert.match(workspaceBlock, /path:\s*"\/dashboard",\s*label:\s*"仪表盘"/)
  assert.match(workspaceBlock, /path:\s*"\/analysis-workbench",\s*label:\s*"自助分析"/)
  assert.match(workspaceBlock, /path:\s*"\/report-center",\s*label:\s*"复杂报表"/)
  assert.doesNotMatch(layout, /path:\s*"\/big-screen-center",\s*label:\s*"大屏中心"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-pipelines",\s*label:\s*"可视化ETL"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/data-pipelines",\s*label:\s*"数据集成管道"/)
  assert.doesNotMatch(biAnalysisBlock, /path:\s*"\/report-center",\s*label:\s*"复杂报表"/)
  assert.doesNotMatch(biAnalysisBlock, /path:\s*"\/analysis-workbench",\s*label:\s*"自助分析"/)
})

test("P1 pages expose production-like API backed workflows", () => {
  for (const path of [
    "src/views/ReportCenter.vue",
    "src/views/ReportDesigner.vue",
    "src/views/DataPipelines.vue",
    "src/views/AnalysisWorkbench.vue",
  ]) {
    assert.ok(existsSync(resolve(root, path)), `${path} should exist`)
  }

  const reportCenter = read("src/views/ReportCenter.vue")
  assert.match(reportCenter, /\/api\/report-templates/)
  assert.match(reportCenter, /复杂报表中心/)
  assert.match(reportCenter, /Excel/)
  assert.match(reportCenter, /PDF/)
  assert.match(reportCenter, /Word/)

  const reportDesigner = read("src/views/ReportDesigner.vue")
  assert.match(reportDesigner, /类 Excel 设计器/)
  assert.match(reportDesigner, /参数报表/)
  assert.match(reportDesigner, /数据填报/)

  const pipelines = read("src/views/DataPipelines.vue")
  assert.match(pipelines, /\/api\/pipelines/)
  assert.match(pipelines, /\/api\/quality-rules/)
  assert.match(pipelines, /可视化ETL/)
  assert.match(pipelines, /VueFlow/)
  assert.match(pipelines, /补数/)

  const workbench = read("src/views/AnalysisWorkbench.vue")
  assert.match(workbench, /\/api\/analysis-views/)
  assert.match(workbench, /拖拽式自助分析/)
  assert.match(workbench, /同环比/)
  assert.match(workbench, /钻取/)
})
