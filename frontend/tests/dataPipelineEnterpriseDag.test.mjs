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

test("data pipeline workbench uses a left operator console and drawer node editing", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /etl-shell--composer/)
  assert.match(pipelines, /操作台/)
  assert.match(pipelines, /class="node-config-drawer"/)
  assert.match(pipelines, /v-model="nodeDrawerVisible"/)
  assert.match(pipelines, /nodeDrawerVisible\.value = true/)
  assert.doesNotMatch(pipelines, /grid-template-columns:\s*292px minmax\(0, 1fr\) 360px/)
})

test("data pipeline workbench loads operator catalog and canvas productivity tools", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /\/api\/pipelines\/operators/)
  assert.match(pipelines, /operatorCatalog/)
  assert.match(pipelines, /operatorGroups/)
  assert.match(pipelines, /MiniMap/)
  assert.match(pipelines, /Controls/)
  assert.match(pipelines, /Background/)
  assert.match(pipelines, /undoDagChange/)
  assert.match(pipelines, /redoDagChange/)
  assert.match(pipelines, /copySelectedNode/)
  assert.match(pipelines, /deleteSelectedNode/)
  assert.match(pipelines, /autoLayoutDag/)
  assert.match(pipelines, /nodeSearch/)
  assert.match(pipelines, /locateSearchedNode/)
})

test("data pipeline workbench exposes inspect/profile and SQL editor affordances", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /\/inspect/)
  assert.match(pipelines, /inspectSelectedNode/)
  assert.match(pipelines, /inspectProfile/)
  assert.match(pipelines, /字段画像/)
  assert.match(pipelines, /CodeMirror/)
  assert.match(pipelines, /sqlEditorExtensions/)
  assert.match(pipelines, /primary_key/)
  assert.match(pipelines, /upsert_keys/)
  assert.match(pipelines, /更新写入/)
})

test("data pipeline workbench applies consistent enterprise toolbar styling", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /pipeline-action-toolbar/)
  assert.match(pipelines, /canvas-commandbar/)
  assert.match(pipelines, /toolbar-group/)
  assert.match(pipelines, /toolbar-button/)
  assert.match(pipelines, /flow-control-button/)
  assert.match(pipelines, /ElTooltip/)
  assert.match(pipelines, /section-heading > div:first-child/)
  assert.doesNotMatch(pipelines, /canvas-toolstrip/)
  assert.doesNotMatch(pipelines, /h\("button"/)
})

test("data pipeline canvas renders compact icon nodes instead of text rectangles", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /#node-etl-icon/)
  assert.match(pipelines, /<Handle type="target"/)
  assert.match(pipelines, /<Handle type="source"/)
  assert.match(pipelines, /etl-canvas-node__icon/)
  assert.match(pipelines, /nodeTypeIcon/)
  assert.match(pipelines, /type:\s*"etl-icon"/)
  assert.match(pipelines, /caption:\s*`\$\{typeLabel\} · \$\{rowsText \|\| statusText\}`/)
  assert.doesNotMatch(pipelines, /white-space:\s*pre-line/)
})
