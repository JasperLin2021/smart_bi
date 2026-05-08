import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("big screen center is a standalone top-level sidebar entry", () => {
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(layout, /type:\s*"item",\s*path:\s*"\/big-screen-center",\s*label:\s*"大屏中心"/)
  assert.match(layout, /<el-menu-item\s+v-if="entry\.type === 'item'"/)
  assert.match(layout, /visibleMenuEntries/)

  const biAssetsBlock = layout.match(/key:\s*"bi-assets"[\s\S]*?key:\s*"system-admin"/)?.[0] || ""
  assert.match(biAssetsBlock, /path:\s*"\/dashboard-center",\s*label:\s*"看板中心"/)
  assert.doesNotMatch(biAssetsBlock, /path:\s*"\/big-screen-center"/)
})
