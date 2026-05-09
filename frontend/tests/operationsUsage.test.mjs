import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("operations backend displays resource usage and operational health", () => {
  const view = read("src/views/Operations.vue")

  assert.match(view, /\/api\/operations\/summary/)
  assert.match(view, /resource_usage/)
  assert.match(view, /asset_health/)
  assert.match(view, /system_resources/)
  assert.match(view, /query_trend/)
  assert.match(view, /datasource_usage/)
  assert.match(view, /资源使用/)
  assert.match(view, /系统资源/)
  assert.match(view, /运行健康/)
  assert.match(view, /近 7 日问数趋势/)
  assert.match(view, /数据源负载排行/)
  assert.match(view, /el-progress/)
})

test("operations dashboard uses icon buttons and compact admin cards", () => {
  const view = read("src/views/Operations.vue")

  assert.match(view, /:icon="Refresh"/)
  assert.match(view, /class="usage-card"/)
  assert.match(view, /class="health-panel"/)
  assert.match(view, /class="trend-bars"/)
  assert.doesNotMatch(view, /<el-button[^>]*>刷新<\/el-button>/)
})
