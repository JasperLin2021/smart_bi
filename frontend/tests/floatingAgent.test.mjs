import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("main layout mounts the floating page agent for authenticated pages", () => {
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(layout, /import FloatingAgent from "@\/components\/FloatingAgent\.vue"/)
  assert.match(layout, /<FloatingAgent \/>/)
})

test("floating agent uses accessible icon controls and responsive panel layout", () => {
  const component = read("src/components/FloatingAgent.vue")

  assert.match(component, /class="agent-fab"/)
  assert.match(component, /aria-label="打开页面 Agent"/)
  assert.match(component, /aria-label="打开 Agent Skills"/)
  assert.match(component, /aria-label="清空 Agent 对话"/)
  assert.match(component, /aria-label="关闭页面 Agent"/)
  assert.match(component, /\.agent-fab\s*\{[\s\S]*?min-width:\s*56px/)
  assert.match(component, /\.agent-fab:focus-visible/)
  assert.match(component, /\.agent-panel\s*\{[\s\S]*?width:\s*min\(420px,\s*calc\(100vw - 32px\)\)/)
  assert.match(component, /@media \(max-width:\s*768px\)/)
})

test("agent store normalizes legacy routes to the current refactored navigation", () => {
  const store = read("src/store/agent.ts")

  assert.match(store, /normalizeAgentRoute/)
  assert.match(store, /"\/datasource-settings":\s*\{\s*path:\s*"\/data-development",\s*query:\s*\{\s*tab:\s*"datasources"\s*\}/)
  assert.match(store, /"\/dataset-center":\s*\{\s*path:\s*"\/data-development",\s*query:\s*\{\s*tab:\s*"datasets"\s*\}/)
  assert.match(store, /"\/user-management":\s*"\/access-control"/)
  assert.match(store, /"\/org-management":\s*"\/access-control"/)
  assert.match(store, /case "create_dataset":/)
  assert.match(store, /case "create_pipeline":/)
  assert.match(store, /case "create_analysis_view":/)
  assert.match(store, /case "create_action_item":/)
  assert.doesNotMatch(store, /await router\.push\(action\.params\.route\)/)
})
