import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("data catalog referenced dashboards open in a preview modal", () => {
  const view = read("src/views/DataCatalog.vue")

  assert.match(view, /catalog-dashboard-preview-dialog/)
  assert.match(view, /dashboardPreviewVisible/)
  assert.match(view, /openDashboardPreview\(r\.id\)/)
  assert.match(view, /\/api\/dashboards\/\$\{id\}/)
  assert.match(view, /看板预览/)
  assert.match(view, /预览看板/)
  assert.match(view, /<el-button[^>]*@click="openDashboardEditorFromPreview"/)
  assert.match(view, /<PinnedChartCard/)
  assert.doesNotMatch(view, /@click="openDashboard\(r\.id\)">打开/)
})

test("dashboard center can open a dashboard designer from catalog query params", () => {
  const view = read("src/views/DashboardCenter.vue")

  assert.match(view, /useRoute/)
  assert.match(view, /openDashboardFromRouteQuery/)
  assert.match(view, /route\.query\.dashboard_id/)
  assert.match(view, /route\.query\.mode === "edit"/)
  assert.match(view, /openDesigner\(target\)/)
})
