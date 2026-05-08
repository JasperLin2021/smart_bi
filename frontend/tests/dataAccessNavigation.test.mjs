import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("data access is an independent top-level sidebar menu", () => {
  const router = read("src/router/index.ts")
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(router, /path:\s*"\/data-access"/)
  assert.match(router, /import\("@\/views\/DataAccessCenter\.vue"\)/)
  assert.match(layout, /key:\s*"data-access"[\s\S]*?label:\s*"数据接入"/)

  const dataAccessBlock = layout.match(/key:\s*"data-access"[\s\S]*?key:\s*"bi-assets"/)?.[0] || ""
  assert.match(dataAccessBlock, /path:\s*"\/data-access",\s*label:\s*"接入总览"/)
  assert.match(dataAccessBlock, /path:\s*"\/datasource-settings",\s*label:\s*"数据源管理"/)
  assert.match(dataAccessBlock, /path:\s*"\/dataset-center",\s*label:\s*"数据集开发"/)
  assert.match(dataAccessBlock, /path:\s*"\/olap-status",\s*label:\s*"数据平台"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-catalog",\s*label:\s*"数据目录"/)
})

test("data access center exposes integration-style operations", () => {
  const view = read("src/views/DataAccessCenter.vue")

  assert.match(view, /数据接入中心/)
  assert.match(view, /\/api\/data-access\/overview/)
  assert.match(view, /多源异构接入/)
  assert.match(view, /数据开发/)
  assert.match(view, /同步与物化/)
  assert.match(view, /任务运维/)
  assert.match(view, /\/datasource-settings/)
  assert.match(view, /\/dataset-center/)
  assert.match(view, /\/olap-status/)
})
