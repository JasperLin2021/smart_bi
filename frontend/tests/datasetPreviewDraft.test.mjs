import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("dataset builder preview uses the current draft dataset payload", () => {
  const view = read("src/views/DatasetCenter.vue")
  const fetchPreviewBlock = view.match(/const fetchPreview = async \(\) => \{[\s\S]*?\n\}/)?.[0] || ""

  assert.match(fetchPreviewBlock, /buildPayload\(\)/)
  assert.match(fetchPreviewBlock, /\/api\/datasets\/preview-draft/)
  assert.doesNotMatch(fetchPreviewBlock, /\/api\/datasources\/\$\{form\.datasource_id\}\/preview/)
})

test("dataset aggregation builder treats measures separately from selected dimensions", () => {
  const view = read("src/views/DatasetCenter.vue")
  const fieldConfigBlock = view.match(/<div class="field-config-list"[\s\S]*?<el-empty/)?.[0] || ""
  const metricExpressionBlock = view.match(/const metricExpressions = computed\(\(\) =>[\s\S]*?\n\)/)?.[0] || ""

  assert.match(fieldConfigBlock, /v-model="config\.role"/)
  assert.match(fieldConfigBlock, /v-model="config\.alias"/)
  assert.match(fieldConfigBlock, /v-if="config\.role === 'metric'"/)
  assert.match(metricExpressionBlock, /config\.aggregation/)
  assert.doesNotMatch(view, /const addAggregation = \(\)/)
})

test("dataset builder persists explicit dimensions separately from aggregate metrics", () => {
  const view = read("src/views/DatasetCenter.vue")
  const buildPayloadBlock = view.match(/const buildPayload = \(\) => \(\{[\s\S]*?\n\}\)/)?.[0] || ""

  assert.match(view, /维度字段/)
  assert.match(view, /指标字段/)
  assert.match(view, /fieldRoleConfigs/)
  assert.match(view, /roleOptions/)
  assert.match(buildPayloadBlock, /dimensions: dimensionPayloads\.value/)
  assert.match(buildPayloadBlock, /metrics: metricPayloads\.value/)
  assert.match(buildPayloadBlock, /aggregations: metricExpressions\.value/)
})

test("organization-visible dataset publishing requires department admin approval", () => {
  const view = read("src/views/DatasetCenter.vue")

  assert.match(view, /pending_review/)
  assert.match(view, /待审批/)
  assert.match(view, /待部门管理员审批/)
  assert.match(view, /approveDataset/)
  assert.match(view, /\/api\/datasets\/\$\{dataset\.id\}\/approve/)
  assert.match(view, /审批发布/)
  assert.match(view, /datasetStatusLabel/)
  assert.match(view, /datasetStatusTagType/)
  assert.match(view, /orgVisibilityApprovalRequired/)
  assert.match(view, /保存后提交审批/)
})

test("dataset field modeling UI is optimized for role-based configuration", () => {
  const view = read("src/views/DatasetCenter.vue")

  assert.match(view, /field-panel-hero/)
  assert.match(view, /field-mode-tabs/)
  assert.match(view, /fieldRoleView/)
  assert.match(view, /model-overview/)
  assert.match(view, /fields-health-pill/)
  assert.match(view, /control-field/)
  assert.match(view, /metricExpressionLabel/)
  assert.match(view, /从左侧字段卡片切换为维度/)
  assert.match(view, /从左侧字段卡片切换为指标/)
})

test("derived column expression candidates come from all configured metrics", () => {
  const view = read("src/views/DatasetCenter.vue")
  const derivedBuilderBlock = view.match(/<section class="advanced-section">[\s\S]*?添加派生列/)?.[0] || ""

  assert.match(view, /derivedMetricCandidates/)
  assert.match(derivedBuilderBlock, /v-if="derivedMetricCandidates\.length"/)
  assert.match(derivedBuilderBlock, /v-for="metric in derivedMetricCandidates"/)
  assert.match(derivedBuilderBlock, /appendDerivedToken\(metric\.expression\)/)
  assert.match(derivedBuilderBlock, /metric\.label/)
  assert.doesNotMatch(derivedBuilderBlock, /v-for="field in selectedColumns"/)
})

test("dataset center uses a compact top-right toolbar instead of hero and summary cards", () => {
  const view = read("src/views/DatasetCenter.vue")

  assert.match(view, /class="dataset-toolbar"/)
  assert.match(view, /class="dataset-toolbar-actions"/)
  assert.match(view, /class="search-input"/)
  assert.match(view, /新建数据集/)
  assert.doesNotMatch(view, /class="dataset-hero"/)
  assert.doesNotMatch(view, /class="hero-actions"/)
  assert.doesNotMatch(view, /class="summary-grid"/)
  assert.doesNotMatch(view, /\.dataset-hero\s*\{/)
  assert.doesNotMatch(view, /\.hero-actions\s*\{/)
  assert.doesNotMatch(view, /\.summary-grid\s*\{/)
})

test("editing an existing dataset automatically refreshes the schema so new fields reach the candidate area", () => {
  const view = read("src/views/DatasetCenter.vue")
  const openEditBlock = view.match(/const openEdit = async \(dataset: DatasetItem\) => \{[\s\S]*?\n\}/)?.[0] || ""

  assert.match(openEditBlock, /drawerVisible\.value = true/)
  assert.match(openEditBlock, /void refreshSchemaFields\(\)/)
})

test("schema refresh merges the live table structure and rebuilds field candidate configs", () => {
  const view = read("src/views/DatasetCenter.vue")
  const refreshBlock = view.match(/const refreshSchemaFields = async \(\) => \{[\s\S]*?\n\}/)?.[0] || ""

  assert.match(refreshBlock, /\/api\/datasources\/\$\{form\.datasource_id\}\/refresh-schema/)
  assert.match(refreshBlock, /fetchDatasourceDetail\(form\.datasource_id\)/)
  assert.match(refreshBlock, /syncFieldRoleConfigs\("suggest"\)/)
})

test("manual schema detection rebuilds the field candidate area even when the main table is already selected", () => {
  const view = read("src/views/DatasetCenter.vue")
  const detectBlock = view.match(/const detectSchema = async \(\) => \{[\s\S]*?\n\}/)?.[0] || ""

  assert.match(detectBlock, /fetchDatasourceDetail\(form\.datasource_id\)/)
  assert.match(detectBlock, /syncFieldRoleConfigs\("suggest"\)/)
})
