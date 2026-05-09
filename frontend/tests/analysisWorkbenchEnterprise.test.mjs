import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const workbench = readFileSync(resolve(root, "src/views/AnalysisWorkbench.vue"), "utf8")

test("analysis workbench previews real API data instead of mock bars", () => {
  assert.match(workbench, /\/api\/analysis-views\/preview-draft/)
  assert.match(workbench, /echarts/)
  assert.doesNotMatch(workbench, /mockBars/)
  assert.doesNotMatch(workbench, /chart-mock/)
  assert.match(workbench, /previewRows/)
  assert.match(workbench, /chartData/)
})

test("analysis workbench exposes enterprise analysis operations", () => {
  for (const token of [
    "维度",
    "指标",
    "筛选",
    "排序",
    "TopN",
    "同环比",
    "占比",
    "排名",
    "累计",
  ]) {
    assert.match(workbench, new RegExp(token))
  }

  assert.match(workbench, /copyAnalysisView/)
  assert.match(workbench, /publishAnalysisView/)
  assert.match(workbench, /addCurrentViewToDashboard/)
  assert.match(workbench, /exportPreview/)
})

test("analysis workbench supports drag interaction and responsive UX states", () => {
  assert.match(workbench, /draggable=/)
  assert.match(workbench, /@dragstart=/)
  assert.match(workbench, /@drop=/)
  assert.match(workbench, /loading/)
  assert.match(workbench, /empty/)
  assert.match(workbench, /hasPreviewRun/)
  assert.match(workbench, /当前条件无数据/)
  assert.match(workbench, /errorMessage/)
})
