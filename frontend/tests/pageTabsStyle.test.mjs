import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("top-level page tabs share the access control tab button style", () => {
  const styles = read("src/styles/index.css")
  const accessControl = read("src/views/AccessControl.vue")
  const dataDevelopment = read("src/views/DataSourceDatasetCenter.vue")
  const wechatWork = read("src/views/WechatWorkIntegration.vue")

  assert.match(styles, /\.page-tabbar[\s\S]*border-radius:\s*12px/)
  assert.match(styles, /\.page-tab[\s\S]*background:\s*transparent/)
  assert.match(styles, /\.page-tab\.is-active[\s\S]*background:\s*var\(--app-primary\)/)
  assert.match(accessControl, /class="page-tabbar ac-tabbar"/)
  assert.match(accessControl, /class="page-tab ac-tab"/)
  assert.match(dataDevelopment, /class="page-tabbar development-tabbar"/)
  assert.match(wechatWork, /class="page-tabbar settings-tabbar"/)
})

test("top-level segmented tab filters opt into the shared page tab skin", () => {
  const dashboard = read("src/views/DashboardCenter.vue")
  const datasets = read("src/views/DatasetCenter.vue")
  const bigScreens = read("src/views/BigScreenCenter.vue")
  const goview = read("src/views/GoViewCenter.vue")

  for (const component of [dashboard, datasets, bigScreens, goview]) {
    assert.match(component, /class="page-segmented-tabs"/)
  }
})
