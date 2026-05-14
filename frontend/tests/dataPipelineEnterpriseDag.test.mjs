import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("data pipeline workbench exposes drag-drop DAG editing and realtime preview", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /draggable="true"/)
  assert.match(pipelines, /@dragstart="onPaletteDragStart\(node\.type\)"/)
  assert.match(pipelines, /@drop\.prevent="onCanvasDrop"/)
  assert.match(pipelines, /@connect="onConnect"/)
  assert.match(pipelines, /@node-drag-stop="onNodeDragStop"/)
  assert.match(pipelines, /dag_json:\s*selectedPipeline\.value\.dag_json/)
})

test("data pipeline workbench exposes SQL, scale pushdown, and reverse ETL operators", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /type:\s*"sql"/)
  assert.match(pipelines, /SQL 算子/)
  assert.match(pipelines, /execution_mode/)
  assert.match(pipelines, /数据库下推/)
  assert.match(pipelines, /type:\s*"reverse_etl"/)
  assert.match(pipelines, /反向 ETL/)
})
