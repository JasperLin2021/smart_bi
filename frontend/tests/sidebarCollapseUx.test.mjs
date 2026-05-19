import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("sidebar collapse exposes a large edge handle in addition to the small header toggle", () => {
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(layout, /effectiveSidebarCollapsed\.value \? "72px" : "224px"/)
  assert.doesNotMatch(layout, /"260px"/)
  assert.match(layout, /class="sidebar-edge-toggle"/)
  assert.match(layout, /v-if="!isMobileLayout"/)
  assert.match(layout, /@click="toggleSidebar"/)
  assert.match(layout, /:aria-label="effectiveSidebarCollapsed \? '展开侧边栏导航' : '收起侧边栏导航'"/)
  assert.match(layout, /:title="effectiveSidebarCollapsed \? '展开侧边栏导航' : '收起侧边栏导航'"/)
  assert.match(layout, /class="visually-hidden"/)
  assert.match(layout, /\.sidebar-edge-toggle\s*\{[\s\S]*?width:\s*44px/)
  assert.match(layout, /\.sidebar-edge-toggle\s*\{[\s\S]*?min-height:\s*96px/)
  assert.match(layout, /\.sidebar-edge-toggle\s*\{[\s\S]*?touch-action:\s*manipulation/)
  assert.match(layout, /\.sidebar-edge-toggle:focus-visible/)
  assert.match(layout, /\.sidebar-edge-grip/)
})
