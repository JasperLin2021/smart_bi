import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { test } from "node:test"
import { fileURLToPath } from "node:url"

let loadedModule

async function loadChartColors() {
  if (loadedModule) return loadedModule

  const testDir = dirname(fileURLToPath(import.meta.url))
  const sourcePath = resolve(testDir, "../src/utils/chartColors.ts")
  assert.ok(existsSync(sourcePath), "chartColors.ts should exist")

  const ts = await import("typescript")
  const source = readFileSync(sourcePath, "utf8")
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText

  const encoded = Buffer.from(output, "utf8").toString("base64")
  loadedModule = await import(`data:text/javascript;base64,${encoded}`)
  return loadedModule
}

test("chart palette keeps the app primary green as the first color", async () => {
  const { CHART_COLOR_PALETTE, PRIMARY_CHART_COLOR } = await loadChartColors()

  assert.equal(PRIMARY_CHART_COLOR, "#0f766e")
  assert.equal(CHART_COLOR_PALETTE[0], PRIMARY_CHART_COLOR)
  assert.ok(new Set(CHART_COLOR_PALETTE).size >= 8)
})

test("category values use multiple colors only when there are multiple items", async () => {
  const { colorizeCategoryData, PRIMARY_CHART_COLOR } = await loadChartColors()

  const single = colorizeCategoryData([12], [3, 3, 0, 0])
  assert.deepEqual(single, [
    { value: 12, itemStyle: { color: PRIMARY_CHART_COLOR, borderRadius: [3, 3, 0, 0] } },
  ])

  const multiple = colorizeCategoryData([12, 24, 36], [3, 3, 0, 0])
  assert.deepEqual(
    multiple.map(item => item.itemStyle.color),
    ["#0f766e", "#3b82f6", "#f59e0b"],
  )
})
