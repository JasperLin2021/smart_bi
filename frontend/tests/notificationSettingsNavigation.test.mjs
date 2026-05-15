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

test("llm settings includes aliyun bailian qwen dashscope preset", () => {
  const llmSettings = read("src/views/LlmSettings.vue")

  assert.match(llmSettings, /label="阿里云百炼（DashScope）"\s+value="dashscope"/)
  assert.match(llmSettings, /dashscope:\s*\{\s*base_url:\s*"https:\/\/dashscope\.aliyuncs\.com\/compatible-mode\/v1",\s*model:\s*"qwen3\.6-35b-a3b"/)
  assert.doesNotMatch(llmSettings, /sk-[a-z0-9]{20,}/i)
})
