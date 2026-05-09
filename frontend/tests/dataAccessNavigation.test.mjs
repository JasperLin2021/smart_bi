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
  assert.match(router, /path:\s*"\/data-development"/)
  assert.match(router, /import\("@\/views\/DataSourceDatasetCenter\.vue"\)/)
  assert.match(router, /path:\s*"\/datasource-settings",\s*redirect:\s*\{\s*path:\s*"\/data-development",\s*query:\s*\{\s*tab:\s*"datasources"\s*\}\s*\}/)
  assert.match(router, /path:\s*"\/dataset-center",\s*redirect:\s*\{\s*path:\s*"\/data-development",\s*query:\s*\{\s*tab:\s*"datasets"\s*\}\s*\}/)
  assert.match(layout, /key:\s*"data-access"[\s\S]*?label:\s*"数据准备"/)

  const dataAccessBlock = layout.match(/key:\s*"data-access"[\s\S]*?key:\s*"bi-assets"/)?.[0] || ""
  assert.match(dataAccessBlock, /path:\s*"\/data-access",\s*label:\s*"准备总览"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-link",\s*label:\s*"连接器接入"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-pipelines",\s*label:\s*"数据加工管道"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-development",\s*label:\s*"数据源与数据集"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/datasource-settings",\s*label:\s*"数据源管理"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/dataset-center",\s*label:\s*"数据集开发"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/data-link",\s*label:\s*"数据接入"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/data-pipelines",\s*label:\s*"数据集成管道"/)
  assert.match(dataAccessBlock, /path:\s*"\/olap-status",\s*label:\s*"OLAP 数据平台"/)
  assert.doesNotMatch(dataAccessBlock, /path:\s*"\/olap-status",\s*label:\s*"数据平台"/)
  assert.match(dataAccessBlock, /path:\s*"\/data-catalog",\s*label:\s*"数据目录"/)
})

test("data source and dataset development share one tabbed workbench", () => {
  const view = read("src/views/DataSourceDatasetCenter.vue")

  assert.match(view, /数据源与数据集/)
  assert.match(view, /数据源管理/)
  assert.match(view, /数据集开发/)
  assert.match(view, /DataSourceSettings/)
  assert.match(view, /DatasetCenter/)
  assert.match(view, /tab:\s*"datasources"/)
  assert.match(view, /tab:\s*"datasets"/)
  assert.match(view, /<el-tabs/)
  assert.doesNotMatch(view, /development-header/)
  assert.doesNotMatch(view, /scope-card/)
  assert.doesNotMatch(view, /DATA WORKBENCH/)
})

test("data access center exposes integration-style operations", () => {
  const view = read("src/views/DataAccessCenter.vue")

  assert.match(view, /数据准备中心/)
  assert.match(view, /\/api\/data-access\/overview/)
  assert.match(view, /连接器接入/)
  assert.match(view, /多源异构接入/)
  assert.match(view, /数据开发/)
  assert.match(view, /同步与物化/)
  assert.match(view, /任务运维/)
  assert.match(view, /OLAP 数据平台/)
  assert.match(view, /\/data-development\?tab=datasources/)
  assert.match(view, /\/data-development\?tab=datasets/)
  assert.match(view, /\/data-pipelines/)
  assert.match(view, /\/olap-status/)
})

test("connector access page is named as connector entry instead of generic data access", () => {
  const view = read("src/views/DataLink.vue")

  assert.match(view, /连接器接入/)
  assert.doesNotMatch(view, /dl-sidebar__title">数据接入/)
})
