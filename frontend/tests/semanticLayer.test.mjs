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

test("semantic query API types are present in frontend-facing code", () => {
  const queryStore = read("src/store/query.ts")

  assert.match(queryStore, /SemanticQueryRequest/)
  assert.match(queryStore, /\/api\/query\/semantic/)
})
