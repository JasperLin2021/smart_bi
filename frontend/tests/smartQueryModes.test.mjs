import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("smart query exposes only business and agentic modes", () => {
  const view = read("src/views/SmartQuery.vue")
  const store = read("src/store/query.ts")
  const authStore = read("src/store/auth.ts")

  assert.match(view, /业务问数/)
  assert.match(view, /探索模式/)
  assert.match(view, /canUseAgenticMode/)
  assert.match(view, /label="agentic"/)
  assert.match(view, /useAuthStore/)
  assert.match(authStore, /canUseAgenticMode/)
  assert.match(authStore, /dept_admin/)
  assert.match(store, /QueryMode = "business" \| "agentic"/)
  assert.match(store, /mode: "business" as QueryMode/)
  assert.doesNotMatch(view, /闲聊模式/)
  assert.doesNotMatch(view, /Agentic 问数/)
  assert.doesNotMatch(view, /label="explore"/)
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
  assert.doesNotMatch(bubble, /探索结果，非认证口径/)
  assert.doesNotMatch(bubble, /message\.mode === ['"]explore['"]/)
})

test("query history provides searchable CRUD controls and a new conversation entry", () => {
  const view = read("src/views/SmartQuery.vue")

  assert.match(view, /新建对话/)
  assert.match(view, /startNewConversation/)
  assert.match(view, /queryStore\.clearMessages\(\)/)
  assert.match(view, /historySearch/)
  assert.match(view, /historyFilter/)
  assert.match(view, /filteredHistory/)
  assert.match(view, /historyEmptyDescription/)
  assert.match(view, /confirmDeleteHistoryItem/)
  assert.match(view, /ElMessageBox\.confirm/)
  assert.match(view, /history-empty-actions/)
  assert.match(view, /收藏/)
  assert.match(view, /清空历史/)
  assert.match(view, /formatHistoryDate/)
})

test("agentic mode is datasource-only and admin roles default into it", () => {
  const view = read("src/views/SmartQuery.vue")
  const store = read("src/store/query.ts")

  assert.match(view, /const isDeptAdminOrAbove = computed/)
  assert.match(view, /applyRoleDefaultMode/)
  assert.match(view, /queryStore\.mode = "agentic"/)
  assert.match(view, /if \(queryStore\.mode === "agentic"\) return Boolean\(queryStore\.selectedDatasourceId\)/)
  assert.match(view, /if \(queryStore\.mode === "agentic"\) return activeDatasource\.value\?\.name \|\| "未选择数据源"/)
  assert.match(view, /if \(queryStore\.mode === "agentic"\) return "数据源"/)
  assert.match(view, /queryStore\.mode === 'agentic'/)
  assert.doesNotMatch(view, /scopeOptions/)
  assert.doesNotMatch(view, /value:\s*"dataset"/)
  assert.doesNotMatch(view, /queryStore\.mode === ['"]explore['"]/)
  assert.doesNotMatch(view, /queryStore\.scopeMode === "dataset" \? "数据集" : "数据源"/)
  assert.match(store, /const datasetId = mode === "business" \? this\.selectedDatasetId : null/)
  assert.match(store, /agentTrace: response\.data\.agent_trace \|\| \[\]/)
  assert.match(store, /data\.mode === "explore" \? "agentic"/)
})

test("agentic query exposes execution trace in chat messages", () => {
  const bubble = read("src/components/ChatBubble.vue")
  const store = read("src/store/query.ts")

  assert.match(bubble, /探索模式执行过程/)
  assert.match(bubble, /message\.status === 'sending'/)
  assert.match(bubble, /message\.agentTrace\?\.length/)
  assert.match(bubble, /trace-step/)
  assert.match(bubble, /trace-detail/)
  assert.match(bubble, /formatTraceDetail/)
  assert.match(bubble, /sql_execute_fix/)
  assert.match(bubble, /chat-error-line/)
  assert.match(store, /ask-stream/)
  assert.match(store, /ReadableStream/)
  assert.match(store, /getReader/)
  assert.match(store, /TextDecoder/)
  assert.match(store, /eventName === "trace"/)
  assert.match(store, /errorDetail/)
  assert.match(store, /agent_trace/)
  assert.match(store, /payloadTrace\.length \? payloadTrace : current\?\.agentTrace \|\| \[\]/)
  assert.match(store, /agentTrace: errorAgentTrace/)
})

test("agentic trace panel is collapsible and expands failed step details", () => {
  const bubble = read("src/components/ChatBubble.vue")

  assert.match(bubble, /agentTracePanelOpen/)
  assert.match(bubble, /traceDetailOpen/)
  assert.match(bubble, /handleTracePanelChange/)
  assert.match(bubble, /defaultTraceDetailNames/)
  assert.match(bubble, /el-collapse v-model="agentTracePanelOpen" class="agent-trace-collapse"/)
  assert.match(bubble, /el-collapse v-model="traceDetailOpen" class="trace-detail-collapse"/)
  assert.match(bubble, /traceSummary/)
  assert.match(bubble, /props\.message\.status === "success"/)
  assert.match(bubble, /失败步骤自动展开/)
})

test("agentic query carries chart spec into the chat chart renderer", () => {
  const bubble = read("src/components/ChatBubble.vue")
  const store = read("src/store/query.ts")
  const chart = read("src/components/MessageChart.vue")

  assert.match(store, /export interface ChartSpec/)
  assert.match(store, /chartSpec\?: ChartSpec/)
  assert.match(store, /chartSpec: payload\.chart_spec/)
  assert.match(store, /chartSpec: response\.data\.chart_spec/)
  assert.match(bubble, /:chart-spec="message\.chartSpec"/)
  assert.match(chart, /chartSpec\?: ChartSpec/)
  assert.match(chart, /applyChartSpec/)
})

test("smart insight panel surfaces llm enhanced state", () => {
  const bubble = read("src/components/ChatBubble.vue")

  assert.match(bubble, /llm_enhanced/)
  assert.match(bubble, /大模型增强/)
  assert.match(bubble, /insightEnhancementLabel/)
  assert.match(bubble, /attributionEnhancementLabel/)
})

test("smart insight actions use grouped asset-oriented UX", () => {
  const bubble = read("src/components/ChatBubble.vue")

  assert.match(bubble, /智能分析/)
  assert.match(bubble, /沉淀资产/)
  assert.match(bubble, /analysis-action-card/)
  assert.match(bubble, /analysis-action-groups/)
  assert.match(bubble, /analysisResultPanels/)
  assert.match(bubble, /insight-panel-collapse/)
  assert.match(bubble, /analysisStatusText/)
  assert.match(bubble, /metricDraftCompletionItems/)
  assert.match(bubble, /metric-draft-checklist/)
  assert.match(bubble, /保存为指标草稿/)
  assert.match(bubble, /保存后会进入指标草稿/)
  assert.match(bubble, /洞察标题/)
  assert.match(bubble, /洞察将保存到查询洞察列表/)
})

test("explore result can be converted into an editable metric draft", () => {
  const bubble = read("src/components/ChatBubble.vue")

  assert.match(bubble, /保存为指标/)
  assert.match(bubble, /metricDraftDrawerVisible/)
  assert.match(bubble, /指标草稿/)
  assert.match(bubble, /\/api\/metrics\/from-query\/draft/)
  assert.match(bubble, /\/api\/metrics\/from-query/)
  assert.match(bubble, /selected_metric_column/)
  assert.match(bubble, /source_query_history_id/)
  assert.match(bubble, /pending_review/)
})

test("natural-language dashboard chart creation uses agentic mode", () => {
  const dashboard = read("src/views/DashboardCenter.vue")

  assert.match(dashboard, /canUseAgenticMode/)
  assert.match(dashboard, /探索模式仅部门管理员及以上可用/)
  assert.match(dashboard, /mode: "agentic"/)
  assert.doesNotMatch(dashboard, /mode: "explore"/)
  assert.doesNotMatch(dashboard, /mode: "text2sql"/)
})
