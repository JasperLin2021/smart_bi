import { test, expect } from "@playwright/test"
import fs from "node:fs"
import path from "node:path"

const outDir = path.resolve(process.cwd(), "tmp-ui-audit")

const now = new Date().toISOString()
const datasources = [
  { id: 101, name: "Nova ERP Warehouse", slug: "nova-erp", source_type: "sqlite", database_url: "sqlite:///nova_erp.db", metadata_prompt: "订单、库存、产线批次", org_id: 1, is_active: 1 },
  { id: 102, name: "Nova Quality Lake", slug: "nova-quality", source_type: "sqlite", database_url: "sqlite:///nova_quality.db", metadata_prompt: "质检批次、良率记录", org_id: 1, is_active: 1 },
]
const datasets = [
  { id: 301, name: "Nova Sales Fulfillment", description: "销售履约分析数据集", datasource_id: 101, status: "published", visibility: "org", org_id: 1, owner_id: 11, fields_json: { table: "sales_orders", fields: ["sales_orders.order_date", "sales_orders.amount"] }, last_refresh_status: "success", last_refresh_row_count: 12480, materialization_status: "ready" },
  { id: 302, name: "Nova Margin Working Draft", description: "毛利测算草稿", datasource_id: 101, status: "draft", visibility: "private", org_id: 1, owner_id: 12, fields_json: { table: "margin_workbench", fields: ["sku", "gross_margin"] }, last_refresh_status: "error", last_refresh_row_count: 0, materialization_status: "pending" },
]
const metrics = [
  { id: 901, name: "On Time Shipment Rate", description: "准时发货率", definition: "准时发货订单 / 全部发货订单", datasource_id: 101, dataset_id: 301, table_name: "shipments", column_name: "on_time_flag", formula: "SUM(on_time) / COUNT(*)", aggregation: "ratio", unit: "%", owner_name: "供应链运营", tags: ["履约", "经营"], status: "published", dimensions: ["plant", "week"], certification_status: "certified", certified_by: "nova.admin", caliber_version: "v2026.05", quality_status: "normal", quality_message: "与月结口径一致", last_value: 96.4, last_computed_at: now, data_updated_at: now, lineage_json: { type: "join_aggregation", source_tables: ["shipments", "orders"], join_conditions: ["shipments.order_id = orders.id"], group_by_fields: ["plant", "week"], aggregate_fields: ["on_time"] } },
  { id: 902, name: "Manufacturing Yield", description: "制造良率", definition: "合格批次数 / 总批次数", datasource_id: 102, dataset_id: null, table_name: "inspection_lots", column_name: "yield_rate", formula: "AVG(yield_rate)", aggregation: "avg", unit: "%", owner_name: "质量经理", tags: ["质量"], status: "published", dimensions: ["line"], certification_status: "pending_review", certified_by: "", caliber_version: "v1", quality_status: "stale", quality_message: "超过 24 小时未刷新", last_value: 98.1, last_computed_at: now, data_updated_at: now, lineage_json: { source_tables: ["inspection_lots"] } },
]
const dashboards = [
  { id: 501, title: "Nova Executive Operations", description: "经营驾驶舱", layout_json: { components: [{ id: "c1", title: "准时发货率", chart_type: "line", pinned_chart_id: 1601, x: 0, y: 0, w: 6, h: 3 }] }, filters_json: {}, status: "published", visibility: "org", is_public: 0, shared_user_ids: [12], version: 2, org_id: 1, owner_id: 11 },
  { id: 502, title: "Quality Daily Review", description: "质量日会看板", layout_json: { components: [] }, status: "draft", visibility: "private", is_public: 0, org_id: 1, owner_id: 12 },
]
const pinnedCharts = [
  { id: 1601, title: "Weekly Revenue", description: "周收入趋势", sql_query: "select week, revenue from finance_weekly", chart_type: "line", sort_order: "desc", display_order: 0, datasource_id: 101, columns: ["week", "revenue"], rows: [{ week: "W18", revenue: 1280000 }, { week: "W19", revenue: 1360000 }, { week: "W20", revenue: 1410000 }] },
  { id: 1602, title: "Yield by Line", description: "产线良率", sql_query: "select line, yield_rate from inspection", chart_type: "bar", sort_order: "desc", display_order: 1, datasource_id: 102, columns: ["line", "yield_rate"], rows: [{ line: "A", yield_rate: 98.6 }, { line: "B", yield_rate: 97.2 }] },
]
const users = [
  { id: 1, username: "root.ops", role: "super_admin", org_id: null, org_name: null, data_scope: null },
  { id: 10, username: "nova.admin", role: "org_admin", org_id: 1, org_name: "Nova Manufacturing", data_scope: "org" },
  { id: 11, username: "nova.analyst", role: "user", org_id: 1, org_name: "Nova Manufacturing", data_scope: "owner" },
]
const organizations = [{ id: 1, name: "Nova Manufacturing", slug: "nova-mfg" }, { id: 2, name: "Orion Retail Group", slug: "orion-retail" }]
const assets = [
  { id: 1201, asset_type: "dataset", asset_id: 301, name: "Nova Sales Fulfillment", description: "已发布销售履约数据集", datasource_id: 101, org_id: 1, owner_id: 11, status: "published", tags: ["销售", "履约"], metadata_json: { fields: { fields: [{ name: "amount", type: "decimal" }] } }, view_count: 128, created_at: now, updated_at: now },
  { id: 1202, asset_type: "metric", asset_id: 901, name: "On Time Shipment Rate", description: "准时发货率指标", datasource_id: 101, org_id: 1, owner_id: 10, status: "published", tags: ["指标"], view_count: 88, created_at: now, updated_at: now },
]
const reportTemplates = [
  { id: 3101, name: "Nova OEE Weekly Report", description: "OEE 周报", dataset_id: 301, report_type: "paginated", status: "published", visibility: "org", version: 2, layout_json: { paper: "A4", cells: [{ row: 1, col: "A", value: "Nova OEE Weekly Report", bold: true }] }, parameter_schema_json: { date_range: { type: "date_range" } }, binding_json: { bands: [{ dataset_id: 301, repeat: "detail" }] }, fill_schema_json: null, created_at: now, updated_at: now },
  { id: 3102, name: "Quality Fill Form", description: "质量填报", dataset_id: 302, report_type: "fill_form", status: "draft", visibility: "org", version: 1, layout_json: { paper: "A4", cells: [] }, parameter_schema_json: {}, binding_json: {}, fill_schema_json: { fields: [{ name: "comment", required: true }] }, created_at: now, updated_at: now },
]
const pipelines = [
  { id: 3201, name: "Nova ERP to Sales Fulfillment", dataset_id: 301, status: "active", last_run_status: "success", dag_json: { nodes: [{ id: "extract", type: "extract", label: "抽取 ERP" }, { id: "quality", type: "quality", label: "质量校验" }, { id: "load", type: "load", label: "写入数据集" }], edges: [{ source: "extract", target: "quality" }, { source: "quality", target: "load" }] } },
]
const qualityRules = [
  { id: 3301, pipeline_id: 3201, dataset_id: 301, name: "金额不能为空", rule_type: "not_null", field: "amount", severity: "error", is_active: true },
]
const analysisViews = [
  { id: 3401, name: "Nova Fulfillment Trend", dataset_id: 301, chart_type: "bar", dimensions: ["order_date"], measures: [{ field: "amount", aggregation: "sum" }], filters: [], status: "published", visibility: "org" },
]

function body(value) {
  return { contentType: "application/json", body: JSON.stringify(value) }
}

async function mockApi(page) {
  await page.route("**/api/**", async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const p = url.pathname
    const ok = (value) => route.fulfill(body(value))
    if (p === "/api/auth/me") return ok(users[0])
    if (p === "/api/auth/login") return ok({ access_token: "ui-audit-token", token_type: "bearer" })
    if (p === "/api/auth/wechat-work/login-url") return ok({ login_url: "https://example.com/wechat-login" })
    if (p === "/api/catalog/notifications") return ok({ items: [], unread_count: 0 })
    if (p === "/api/datasources") return ok(datasources)
    if (/^\/api\/datasources\/\d+$/.test(p)) return ok(datasources[0])
    if (p.includes("/preview")) return ok({ columns: ["week", "amount"], rows: [{ week: "W18", amount: 1280000 }, { week: "W19", amount: 1360000 }] })
    if (p === "/api/query/history") return ok({ items: [] })
    if (p.includes("/rls") || p.includes("/history") || p.includes("/logs")) return ok([])
    if (p.includes("/test")) return ok({ status: "ok", message: "连接成功" })
    if (p.includes("/generate-prompt")) return ok({ metadata_prompt: "自动识别的表结构说明" })
    if (p.includes("/generate-drill-config")) return ok({ dimensions: [], metrics: [], paths: [] })
    if (p === "/api/datasets") return ok({ items: datasets })
    if (/^\/api\/datasets\/\d+$/.test(p)) return ok(datasets[0])
    if (p.includes("/semantic-model")) return ok({ dataset_id: 301, semantic_model: { entities: [{ name: "订单", table: "sales_orders" }], metrics: [{ name: "订单金额", expr: "SUM(amount)" }] }, valid: true })
    if (p === "/api/dashboards") return ok({ items: dashboards })
    if (/^\/api\/dashboards\/\d+$/.test(p)) return ok(dashboards[0])
    if (p === "/api/pinned-charts" || p === "/api/pinned-charts/with-data") return ok(pinnedCharts)
    if (p === "/api/pinned-charts/preview") return ok({ columns: ["week", "revenue"], rows: pinnedCharts[0].rows })
    if (p === "/api/big-screens") return ok({ items: [{ id: 701, title: "Plant Floor Wallboard", description: "产线现场大屏", canvas_json: { widgets: [] }, status: "published", visibility: "org", org_id: 1, owner_id: 10 }] })
    if (p === "/api/metrics") return ok({ items: metrics })
    if (p === "/api/metrics/certifiers") return ok({ items: users.filter(u => u.role !== "user").map(u => ({ ...u, can_certify_metric: true })) })
    if (/^\/api\/metrics\/\d+\/lineage$/.test(p)) return ok({ metric: metrics[0], dataset: datasets[0], datasource: datasources[0], source: { table_name: "shipments", column_name: "on_time_flag", lineage: metrics[0].lineage_json }, trust: { certification_status: "certified", quality_status: "normal", certified_by: "nova.admin", certified_at: now, data_updated_at: now, quality_message: "正常" }, usage: {} })
    if (p.includes("/compute")) return ok({ last_value: 96.7, computed_at: now })
    if (p.includes("/generate-formula")) return ok({ formula: "SUM(on_time) / COUNT(*)" })
    if (p === "/api/alerts") return ok({ items: [{ id: 1001, name: "SLA Risk Alert", datasource_id: 101, metric_id: 901, metric_name: "On Time Shipment Rate", time_range: 1, time_range_unit: "day", check_period: 1, check_period_unit: "hour", notify_system: true, notify_email: false, is_active: true, created_by: 10 }], total: 1 })
    if (p === "/api/scheduled-reports") return ok({ items: [{ id: 1101, name: "Daily Operations Brief", datasource_id: 101, question: "总结昨日订单、库存与风险", cron_expression: "0 9 * * 1-5", notify_email: true, email_recipients: "ops@example.com", is_active: true, created_by: 10, last_run_at: now, created_at: now }], total: 1 })
    if (p === "/api/users/assignable") return ok([{ department: "运营部", users: users.map(u => ({ id: u.id, username: u.username, role: u.role, role_label: u.role, department: "运营部" })) }])
    if (p === "/api/users") return ok(users)
    if (p === "/api/organizations") return ok(organizations)
    if (p === "/api/action-items") return ok({ items: [{ id: 2001, title: "复核 B 线良率异常", description: "B 线良率连续两天低于阈值", source_type: "alert", linked_metric_id: 902, owner_id: 11, priority: "high", status: "open", org_id: 1, created_by: 10, created_at: now, updated_at: now }], total: 1 })
    if (p === "/api/catalog/assets") return ok({ items: assets })
    if (p === "/api/catalog/categories") return ok([{ id: 1, name: "经营分析", parent_id: null, org_id: 1, children: [] }])
    if (/^\/api\/catalog\/assets\/\d+\/fields$/.test(p)) return ok({ columns: [{ name: "amount", type: "decimal", description: "订单金额" }] })
    if (/^\/api\/catalog\/assets\/\d+\/preview$/.test(p)) return ok({ columns: ["week", "amount"], rows: [{ week: "W18", amount: 1280000 }] })
    if (/^\/api\/catalog\/assets\/\d+\/lineage$/.test(p)) return ok({ nodes: [], edges: [] })
    if (/^\/api\/catalog\/assets\/\d+\/references$/.test(p)) return ok({ count: 1, references: [{ type: "dashboard", name: "Nova Executive Operations" }] })
    if (/^\/api\/catalog\/assets\/\d+\/subscription$/.test(p)) return ok({ subscribed: false })
    if (p === "/api/data-access/overview") return ok({ datasources: { total: 2, schema_ready: 2, active: 2 }, datasets: { total: 2, published: 1, materialized: 1 }, sync_tasks: { success: 16, failed: 1 }, olap: { enabled: true, healthy: true }, source_types: [{ type: "sqlite", count: 2 }], recent_refresh_logs: [{ id: 1, dataset_id: 301, status: "success", row_count: 12480, message: "刷新成功", created_at: now }] })
    if (p === "/api/report-templates") return ok({ items: reportTemplates, total: reportTemplates.length })
    if (/^\/api\/report-templates\/\d+$/.test(p)) return ok(reportTemplates[0])
    if (/^\/api\/report-templates\/\d+\/versions$/.test(p)) return ok([{ id: 1, template_id: 3101, version: 2, snapshot_json: reportTemplates[0], changelog: "增加动态收件人", created_at: now }])
    if (/^\/api\/report-templates\/\d+\/export$/.test(p)) return ok({ status: "queued", run_id: 1, export_type: "excel" })
    if (p === "/api/pipelines") return ok(pipelines)
    if (/^\/api\/pipelines\/\d+$/.test(p)) return ok(pipelines[0])
    if (/^\/api\/pipelines\/\d+\/run$/.test(p)) return ok({ id: 1, pipeline_id: 3201, mode: "manual", status: "success", records_read: 360, records_written: 360, records_failed: 0, node_logs_json: { summary: { node_count: 3 } } })
    if (p === "/api/quality-rules") return ok(qualityRules)
    if (p === "/api/analysis-views") return ok({ items: analysisViews, total: analysisViews.length })
    if (/^\/api\/analysis-views\/\d+$/.test(p)) return ok(analysisViews[0])
    if (/^\/api\/analysis-views\/\d+\/preview$/.test(p)) return ok({ query_plan: { sql: "SELECT order_date, SUM(amount) AS sum_amount FROM sales_orders GROUP BY order_date LIMIT 200" }, chart: { type: "bar" }, dataset: datasets[0] })
    if (p === "/api/access-requests") return ok([{ id: 1401, requester_id: 11, resource_type: "dataset", resource_id: 301, resource_name: "Nova Sales Fulfillment", reason: "月度经营复盘", status: "pending", org_id: 1, created_at: now }])
    if (p === "/api/audit-logs") return ok({ total: 1, items: [{ id: 1, actor_username: "nova.admin", actor_role: "org_admin", action: "dashboard.update", resource_type: "dashboard", resource_name: "Nova Executive Operations", status: "success", message: "看板已更新", created_at: now }] })
    if (p === "/api/operations/summary") return ok({ user_count: 6, org_count: 2, datasource_count: 2, query_count: 128, audit_error_count: 0, asset_count: 12, recent_queries: [], recent_audits: [] })
    if (p === "/api/settings/llm") return ok({ provider: "openai", base_url: "https://api.openai.com/v1", model: "gpt-4o-mini", temperature: 0.2, api_key_set: true, agent_planner_mode: "llm_only" })
    if (p === "/api/settings/notification") return ok({ wechat_enabled: false, dingtalk_enabled: false, dingtalk_secret_set: false, email_enabled: true, smtp_host: "smtp.example.com", smtp_port: 465, smtp_username: "bi@example.com", smtp_password_set: true, smtp_from: "bi@example.com", smtp_use_ssl: true })
    if (p === "/api/integrations/wechat-work/config") return ok({ enabled: false, name: "企业微信", corp_id: "", agent_id: "", app_secret_set: false, callback_url: "", robot_webhook_url: "" })
    if (p.includes("/integrations/wechat-work/")) return ok([])
    if (p === "/api/olap/status") return ok({ enabled: true, healthy: true, database: "smart_bi", message: "Doris ready", materialized_dataset_count: 1 })
    if (p === "/api/goview/launch") return ok({
      enabled: true,
      reachable: true,
      title: "GoView",
      modes: ["view", "design"],
      default_mode: "design",
      embed: true,
      organization: { id: 1, name: "Nova Manufacturing", scope: "org" },
      targets: {
        design: "http://127.0.0.1:5174/embed/mock-token",
        view: "http://127.0.0.1:5174/embed/mock-token",
      },
    })
    if (p.startsWith("/api/embed/public/")) return ok({ resource_type: "chart", resource_id: 1601, title: "Weekly Revenue", chart_type: "line", columns: ["week", "revenue"], rows: pinnedCharts[0].rows })
    return ok(req.method() === "GET" ? {} : { ok: true })
  })
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const body = document.body
    const app = document.querySelector("#app")
    const visibleText = (app?.innerText || "").replace(/\s+/g, " ").trim()
    const horizontalOverflow = Math.max(document.documentElement.scrollWidth, body.scrollWidth) - window.innerWidth
    const visibleElements = Array.from(document.querySelectorAll("body *")).filter((el) => {
      const rect = el.getBoundingClientRect()
      const style = getComputedStyle(el)
      return rect.width > 1 && rect.height > 1 && style.visibility !== "hidden" && style.display !== "none"
    })
    const ignoredOverflowSelector = ".el-table, .el-scrollbar, .el-tabs__nav-scroll, .el-tabs__nav-wrap, .grid-stage, .vue-flow__transformationpane, .vue-flow__edge-labels, .vue-flow__nodes"
    const ignoredTags = new Set(["svg", "path", "defs", "clipPath", "g", "col", "colgroup", "thead", "tbody", "tr"])
    const badBounds = visibleElements
      .filter((el) => {
        if (ignoredTags.has(el.tagName.toLowerCase())) return false
        if (horizontalOverflow <= 2 && el.closest(ignoredOverflowSelector)) return false
        const rect = el.getBoundingClientRect()
        return rect.right > window.innerWidth + 2 || rect.left < -2
      })
      .slice(0, 10)
      .map((el) => {
        const rect = el.getBoundingClientRect()
        return { tag: el.tagName.toLowerCase(), className: String(el.className || "").slice(0, 100), text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 70), left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) }
      })
    return { visibleTextLength: visibleText.length, textSample: visibleText.slice(0, 180), horizontalOverflow, badBounds, pathname: location.pathname }
  })
}

test("UI/UX route audit across desktop tablet and mobile", async ({ page }) => {
  test.setTimeout(180000)
  fs.mkdirSync(outDir, { recursive: true })
  const consoleErrors = []
  page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()) })
  page.on("pageerror", err => consoleErrors.push(`pageerror: ${err.message}`))
  await mockApi(page)
  await page.addInitScript(() => localStorage.setItem("smart-bi-token", "ui-audit-token"))

  const routes = ["/login", "/dashboard", "/dashboard-center", "/big-screen-center", "/data-access", "/data-pipelines", "/data-catalog", "/dataset-center", "/smart-query", "/action-items", "/datasource-settings", "/olap-status", "/user-management", "/org-management", "/metric-settings", "/alert-settings", "/report-center", "/report-designer/3101", "/analysis-workbench", "/scheduled-reports", "/audit-logs", "/operations", "/llm-settings", "/notification-settings", "/wechat-work-integration", "/embed/mock-token"]
  const viewports = [
    { name: "desktop", width: 1440, height: 900 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "mobile", width: 390, height: 844 },
  ]
  const screenshotRoutes = new Set(["/login", "/dashboard", "/dashboard-center", "/data-catalog", "/dataset-center", "/smart-query", "/metric-settings", "/report-center", "/data-pipelines", "/analysis-workbench"])
  const results = []

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height })
    for (const routePath of routes) {
      const beforeErrorCount = consoleErrors.length
      await page.goto(`http://127.0.0.1:5174${routePath}`, { waitUntil: "domcontentloaded" })
      await page.waitForTimeout(500)
      const metricsResult = await collectMetrics(page)
      const finding = { viewport: vp.name, route: routePath, ...metricsResult, newErrors: consoleErrors.slice(beforeErrorCount) }
      results.push(finding)
      if (screenshotRoutes.has(routePath) && (vp.name === "desktop" || vp.name === "mobile")) {
        const fileSafe = `${vp.name}-${routePath.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "root"}.png`
        await page.screenshot({ path: path.join(outDir, fileSafe), fullPage: true })
      }
    }
  }

  const failures = results.filter(r => r.visibleTextLength < 20 || r.horizontalOverflow > 2 || r.newErrors.length || r.badBounds.length)
  fs.writeFileSync(path.join(outDir, "ui-audit-results.json"), JSON.stringify({ checked: results.length, failures, consoleErrors, results }, null, 2))
  expect(failures).toEqual([])
})
