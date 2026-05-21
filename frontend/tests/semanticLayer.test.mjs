import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("dataset center exposes semantic layer editing actions", () => {
  const view = read("src/views/DatasetCenter.vue")

  assert.match(view, /语义层/)
  assert.match(view, /semanticModelVisible/)
  assert.match(view, /\/api\/datasets\/\$\{semanticDataset\.id\}\/semantic-model/)
  assert.match(view, /\/api\/datasets\/\$\{semanticDataset\.id\}\/validate-semantic-model/)
})

test("dataset editor supports ai semantic and drill configuration", () => {
  const view = read("src/views/DatasetCenter.vue")
  const queryStore = read("src/store/query.ts")
  const chart = read("src/components/MessageChart.vue")
  const table = read("src/components/MessageTable.vue")

  assert.match(view, /AI 自动配置/)
  assert.match(view, /generateDatasetAiConfig/)
  assert.match(view, /\/api\/datasets\/ai-config\/suggest/)
  assert.match(view, /下钻配置/)
  assert.match(view, /drill_config_json/)
  assert.match(view, /semantic_model_json/)
  assert.match(view, /drillConfig/)
  assert.match(view, /addDrillPath/)
  assert.match(view, /removeDrillPath/)
  assert.match(queryStore, /datasetId\?: number \| null/)
  assert.match(queryStore, /dataset_id: datasetId \|\| null/)
  assert.match(chart, /props\.message\.semanticContext\?\.dataset\?\.id/)
  assert.match(table, /props\.message\.semanticContext\?\.dataset\?\.id/)
})

test("semantic query API types are present in frontend-facing code", () => {
  const queryStore = read("src/store/query.ts")

  assert.match(queryStore, /SemanticQueryRequest/)
  assert.match(queryStore, /\/api\/query\/semantic/)
})
