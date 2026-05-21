import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("login page exposes WeChat Work login entry", () => {
  const view = read("src/views/Login.vue")

  assert.match(view, /企业微信登录/)
  assert.match(view, /\/api\/auth\/wechat-work\/login-url/)
  assert.match(view, /window\.location\.href = data\.login_url/)
})

test("WeChat Work integration has system-admin route and menu", () => {
  const router = read("src/router/index.ts")
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(router, /path:\s*"\/wechat-work-integration"/)
  assert.match(router, /import\("@\/views\/WechatWorkIntegration\.vue"\)/)
  assert.match(layout, /path:\s*"\/wechat-work-integration",\s*label:\s*"企业微信集成"/)
})

test("WeChat Work integration page manages config mappings and deliveries without secret echo", () => {
  const view = read("src/views/WechatWorkIntegration.vue")

  assert.match(view, /企业微信集成/)
  assert.match(view, /\/api\/integrations\/wechat-work\/config/)
  assert.match(view, /\/api\/integrations\/wechat-work\/org-bindings/)
  assert.match(view, /\/api\/integrations\/wechat-work\/permission-mappings/)
  assert.match(view, /\/api\/integrations\/wechat-work\/message-deliveries/)
  assert.match(view, /\/api\/integrations\/wechat-work\/message\/test/)
  assert.match(view, /class="page-tabbar settings-tabbar"/)
  assert.match(view, /class="page-tab"/)
  assert.doesNotMatch(view, /<el-tabs v-model="activeTab" class="settings-tabs"/)
  assert.match(view, /app_secret_set \? '已设置，留空保持不变' : '请输入应用 Secret'/)
  assert.doesNotMatch(view, /{{\s*config\.app_secret\s*}}/)
})
