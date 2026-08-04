import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("vendored echarts runtime is available for generated report HTML", () => {
  assert.ok(existsSync(resolve(root, "public/report-libs/echarts.min.js")))
  assert.match(read("src/views/AiReportLab.vue"), /sandbox="allow-scripts"/)
})

test("ai report lab streams chat via agent-api with a sandboxed preview iframe", () => {
  const view = read("src/views/AiReportLab.vue")

  assert.match(view, /\/agent-api\/reports\/chat/)
  assert.match(view, /conversation_id/)
  assert.match(view, /localStorage\.getItem\("smart-bi-token"\)/)
  assert.match(view, /Authorization: `Bearer \$\{token\}`/)
  assert.match(view, /eventName === "trace"/)
  assert.match(view, /eventName === "report"/)
  assert.match(view, /eventName === "final"/)
  assert.match(view, /eventName === "error"/)
  assert.match(view, /sandbox="allow-scripts"/)
  assert.match(view, /:srcdoc="reportHtml"/)
  assert.doesNotMatch(view, /allow-same-origin/)
  assert.doesNotMatch(view, /v-html/)
})

test("ai report lab toolbar saves, shares and publishes reports", () => {
  const view = read("src/views/AiReportLab.vue")

  assert.match(view, /axios\.post\("\/api\/ai-reports"/)
  assert.match(view, /\/api\/ai-reports\/\$\{id\}\/share/)
  assert.match(view, /\/api\/ai-reports\/\$\{id\}\/publish-to-report-center/)
  assert.match(view, /axios\.get\("\/api\/ai-reports"\)/)
  assert.match(view, /\/report-shared\/\$\{data\.share_token\}/)
  assert.match(view, /保存报表/)
  assert.match(view, /转入报表中心/)
  assert.match(view, /历史报表/)
})

test("shared ai report page is public and renders a sandboxed fullscreen iframe", () => {
  const view = read("src/views/SharedAiReport.vue")
  const router = read("src/router/index.ts")

  assert.match(view, /\/api\/ai-reports\/shared\//)
  assert.match(view, /sandbox="allow-scripts"/)
  assert.match(view, /:srcdoc="reportHtml"/)
  assert.doesNotMatch(view, /allow-same-origin/)
  assert.match(router, /path: "\/report-shared\/:token"[\s\S]+meta: \{ public: true \}/)
})

test("ai report routes, menu entry and dev proxy are registered", () => {
  const router = read("src/router/index.ts")
  const layout = read("src/layouts/MainLayout.vue")
  const vite = read("vite.config.ts")

  assert.match(router, /path: "\/ai-report", component: \(\) => import\("@\/views\/AiReportLab\.vue"\)/)
  assert.match(layout, /\{ path: "\/ai-report", label: "AI 报表", icon: MagicStick \}/)
  assert.match(vite, /"\/agent-api"/)
  assert.match(vite, /VITE_AGENT_PROXY_TARGET/)
  assert.match(vite, /rewrite: \(p\) => p\.replace\(\/\^\\\/agent-api\/, ""\)/)
})

test("report center previews ai_html templates in a sandboxed dialog", () => {
  const view = read("src/views/ReportCenter.vue")

  assert.match(view, /row\.report_type === 'ai_html'/)
  assert.match(view, /ai_html: "AI 报表"/)
  assert.match(view, /openAiPreview/)
  assert.match(view, /\/api\/report-templates\/\$\{row\.id\}/)
  assert.match(view, /layout_json\?\.html/)
  assert.match(view, /sandbox="allow-scripts"/)
  assert.doesNotMatch(view, /allow-same-origin/)
})
