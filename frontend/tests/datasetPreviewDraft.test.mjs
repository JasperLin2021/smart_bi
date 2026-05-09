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
