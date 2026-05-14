import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("data source management does not show configuration completion", () => {
  const view = read("src/views/DataSourceSettings.vue")

  assert.doesNotMatch(view, /配置完成度/)
  assert.doesNotMatch(view, /datasourceCompletion/)
  assert.match(view, /label="表结构"/)
  assert.match(view, /schemaTablesCount\(row\)/)
  assert.match(view, /row\.drill_config \? '已配置钻取' : '未配置钻取'/)
})
