import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("metric lineage visually distinguishes join aggregation metrics from single-table metrics", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /多表 Join 聚合/)
  assert.match(view, /isJoinAggregationLineage/)
  assert.match(view, /lineage-complexity-banner/)
  assert.match(view, /lineage-step--aggregate/)
  assert.match(view, /join_conditions/)
  assert.match(view, /group_by_fields/)
  assert.match(view, /source_tables/)
  assert.match(view, /单表指标/)
})
