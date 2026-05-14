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

test("data pipeline workbench uses a left operator console and pinned node inspector", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /etl-shell--composer/)
  assert.match(pipelines, /操作台/)
  assert.match(pipelines, /node-config-panel--inspector/)
  assert.match(pipelines, /<aside class="node-config-panel node-config-panel--inspector"/)
  assert.match(pipelines, /grid-template-columns:\s*280px minmax\(0, 1fr\) 320px/)
  assert.match(pipelines, /nodeDrawerVisible\.value = true/)
  assert.doesNotMatch(pipelines, /grid-template-columns:\s*292px minmax\(0, 1fr\) 360px/)
})

test("data pipeline workbench loads operator catalog and canvas productivity tools", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /\/api\/pipelines\/operators/)
  assert.match(pipelines, /operatorCatalog/)
  assert.match(pipelines, /operatorGroups/)
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

test("data pipeline node inspector exposes complete executable operator settings", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /物化模式/)
  assert.match(pipelines, /追加物化/)
  assert.match(pipelines, /selectedNodeConfig\.fail_fast/)
  assert.match(pipelines, /失败即阻断后续输出/)
  assert.match(pipelines, /保留首条/)
  assert.match(pipelines, /保留末条/)
  assert.match(pipelines, /datasourceOptions/)
  assert.match(pipelines, /fieldCandidates/)
  assert.match(pipelines, /写入批次大小/)
  assert.match(pipelines, /batch_size/)
  assert.doesNotMatch(pipelines, /<el-input-number v-model="selectedNodeConfig\.datasource_id"/)
})

test("data pipeline workbench applies consistent enterprise toolbar styling", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /pipeline-action-toolbar/)
  assert.match(pipelines, /etl-mode-tabs__actions/)
  assert.match(pipelines, /canvas-commandbar/)
  assert.match(pipelines, /toolbar-group/)
  assert.match(pipelines, /toolbar-button/)
  assert.match(pipelines, /flow-control-button/)
  assert.match(pipelines, /ElTooltip/)
  assert.match(pipelines, /section-heading > div:first-child/)
  assert.doesNotMatch(pipelines, /legacy-commandbar/)
  assert.doesNotMatch(pipelines, /pipeline-kpis/)
  assert.doesNotMatch(pipelines, /summaryStats/)
  assert.doesNotMatch(pipelines, /生产管道/)
  assert.doesNotMatch(pipelines, /SLA ≤ 2h/)
  assert.doesNotMatch(pipelines, /canvas-toolstrip/)
  assert.doesNotMatch(pipelines, /h\("button"/)
})

test("data pipeline canvas renders compact icon nodes instead of text rectangles", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /#node-etl-icon/)
  assert.match(pipelines, /<Handle id="in" type="target" :position="Position\.Left"/)
  assert.match(pipelines, /<Handle id="out" type="source" :position="Position\.Right"/)
  assert.match(pipelines, /etl-canvas-node__icon/)
  assert.match(pipelines, /<el-icon><component :is="data\.icon"/)
  assert.match(pipelines, /nodeTypeIcon/)
  assert.match(pipelines, /nodeTone/)
  assert.match(pipelines, /type:\s*"etl-icon"/)
  assert.match(pipelines, /caption:\s*`\$\{typeLabel\} · \$\{rowsText \|\| statusText\}`/)
  assert.doesNotMatch(pipelines, /white-space:\s*pre-line/)
  assert.doesNotMatch(pipelines, /etl-canvas-node__glyph/)
})

test("data pipeline canvas uses orthogonal left-to-right connectors", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /sourcePosition:\s*Position\.Right/)
  assert.match(pipelines, /targetPosition:\s*Position\.Left/)
  assert.match(pipelines, /type:\s*"step"/)
  assert.match(pipelines, /MarkerType\.ArrowClosed/)
  assert.match(pipelines, /sourceHandle:\s*String\(edge\.sourceHandle \|\| "out"\)/)
  assert.match(pipelines, /targetHandle:\s*String\(edge\.targetHandle \|\| "in"\)/)
  assert.match(pipelines, /buildOrthogonalLayout/)
  assert.match(pipelines, /vue-flow__handle-left/)
  assert.match(pipelines, /vue-flow__handle-right/)
  assert.doesNotMatch(pipelines, /:position="Position\.Top"/)
  assert.doesNotMatch(pipelines, /:position="Position\.Bottom"/)
})

test("data pipeline operator console uses consistent icon-over-text palette cards", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.match(pipelines, /class="source-palette"/)
  assert.match(pipelines, /class="source-chip palette-card"/)
  assert.match(pipelines, /class="palette-card__icon etl-canvas-node__icon"/)
  assert.match(pipelines, /class="palette-card__copy"/)
  assert.match(pipelines, /paletteNodeDescription\(node\)/)
  assert.match(pipelines, /\.source-palette,[\s\S]*?\.node-palette\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(pipelines, /\.palette-card__copy strong/)
  assert.match(pipelines, /\.palette-card__copy small/)
})

test("data pipeline canvas does not render a minimap overview", () => {
  const pipelines = read("src/views/DataPipelines.vue")

  assert.doesNotMatch(pipelines, /<MiniMap/)
  assert.doesNotMatch(pipelines, /画布概览/)
  assert.doesNotMatch(pipelines, /miniMapNodes/)
  assert.doesNotMatch(pipelines, /miniMapSummary/)
  assert.doesNotMatch(pipelines, /flow-minimap/)
  assert.match(pipelines, /<Controls \/>/)
})
