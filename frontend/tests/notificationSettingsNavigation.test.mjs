import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("notification settings is a standalone system-admin menu route", () => {
  const router = read("src/router/index.ts")
  const layout = read("src/layouts/MainLayout.vue")

  assert.match(router, /path:\s*"\/notification-settings"/)
  assert.match(router, /import\("@\/views\/NotificationSettings\.vue"\)/)
  assert.match(layout, /path:\s*"\/notification-settings",\s*label:\s*"通知配置"/)
})

test("llm settings no longer owns notification channel settings", () => {
  const llmSettings = read("src/views/LlmSettings.vue")

  assert.doesNotMatch(llmSettings, /通知渠道配置/)
  assert.doesNotMatch(llmSettings, /\/api\/settings\/notification/)
})
