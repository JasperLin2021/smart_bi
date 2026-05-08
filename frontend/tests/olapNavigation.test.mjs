import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("data platform status has a system route and menu item", () => {
  const router = read("src/router/index.ts")
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(router, /path:\s*"\/olap-status"/)
  assert.match(router, /import\("@\/views\/OlapStatus\.vue"\)/)
  assert.match(layout, /path:\s*"\/olap-status",\s*label:\s*"数据平台"/)
})

test("olap status view calls Doris platform APIs", () => {
  const view = read("src/views/OlapStatus.vue")

  assert.match(view, /\/api\/olap\/status/)
  assert.match(view, /\/api\/datasets\/\$\{dataset\.id\}\/materialize/)
  assert.match(view, /Doris/)
})
