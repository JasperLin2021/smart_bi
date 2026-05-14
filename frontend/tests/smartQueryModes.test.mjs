import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("smart query replaces casual chat with role-gated exploration mode", () => {
  const view = read("src/views/SmartQuery.vue")
  const store = read("src/store/query.ts")
  const authStore = read("src/store/auth.ts")

  assert.match(view, /业务问数/)
  assert.match(view, /探索模式/)
  assert.match(view, /canUseExploreMode/)
  assert.match(view, /v-if="canUseExploreMode"/)
  assert.match(view, /useAuthStore/)
  assert.match(authStore, /canUseExploreMode/)
  assert.match(authStore, /dept_admin/)
  assert.match(store, /QueryMode = "business" \| "explore"/)
  assert.match(store, /mode: "business" as QueryMode/)
  assert.doesNotMatch(view, /闲聊模式/)
  assert.doesNotMatch(view, /label="chat"/)
  assert.doesNotMatch(store, /"chat"/)
})

test("business query defaults to dataset scope and hides SQL behind technical details", () => {
  const view = read("src/views/SmartQuery.vue")
  const store = read("src/store/query.ts")
  const bubble = read("src/components/ChatBubble.vue")

  assert.match(store, /scopeMode: "dataset" as QueryScopeMode/)
  assert.match(view, /queryStore\.mode === "business"/)
  assert.match(view, /业务问数必须选择数据集/)
  assert.match(view, /默认使用可信指标和数据集语义层/)
  assert.match(bubble, /技术细节/)
  assert.match(bubble, /探索结果，非认证口径/)
  assert.match(bubble, /message\.mode === ['"]explore['"]/)
})

test("natural-language dashboard chart creation is treated as gated exploration", () => {
  const dashboard = read("src/views/DashboardCenter.vue")

  assert.match(dashboard, /canUseExploreMode/)
  assert.match(dashboard, /自然语言探索仅部门管理员及以上可用/)
  assert.match(dashboard, /mode: "explore"/)
  assert.doesNotMatch(dashboard, /mode: "text2sql"/)
})
