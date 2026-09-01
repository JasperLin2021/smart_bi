import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("trusted metrics alerts and scheduled reports live under BI analysis menu", () => {
  const layout = read("src/layouts/MainLayout.vue")

  const biAnalysisBlock = layout.match(/key:\s*"bi-assets"[\s\S]*?key:\s*"system-admin"/)?.[0] || ""
  assert.match(biAnalysisBlock, /path:\s*"\/dashboard-center",\s*label:\s*"看板中心"/)
  assert.match(biAnalysisBlock, /path:\s*"\/metric-settings",\s*label:\s*"可信指标"/)
  assert.match(biAnalysisBlock, /path:\s*"\/alert-settings",\s*label:\s*"预警管理"/)
  assert.match(biAnalysisBlock, /path:\s*"\/scheduled-reports",\s*label:\s*"定时报告"/)
  assert.doesNotMatch(layout, /key:\s*"data-governance"/)
})

test("metric creation uses a system-user tree selector for certifier", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /<el-tree-select/)
  assert.match(view, /\/api\/metrics\/certifiers/)
  assert.match(view, /certifierTreeData/)
  assert.match(view, /certified_by:\s*form\.value\.certified_by/)
  assert.match(view, /请选择认证人/)
})

test("metric creation binds trusted metrics to datasets only", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /\/api\/datasets/)
  assert.match(view, /v-model="form\.dataset_id"/)
  assert.match(view, /请选择数据集/)
  assert.match(view, /dataset_id:\s*form\.value\.dataset_id/)
  assert.doesNotMatch(view, /v-model="form\.datasource_id"/)
  assert.doesNotMatch(view, /datasource_id:\s*form\.value\.datasource_id/)
})

test("metric calculation caliber supports enterprise-grade structured rules", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /enterprise-caliber-workbench/)
  assert.match(view, /口径成熟度/)
  assert.match(view, /计算模型/)
  assert.match(view, /统计范围/)
  assert.match(view, /过滤 \/ 排除规则/)
  assert.doesNotMatch(view, /边界与质量规则/)
  assert.doesNotMatch(view, /caliber-boundary-grid/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.null_handling"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.dedup_key"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.denominator_zero_policy"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.exception_handling"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.validation_rule"/)
  assert.doesNotMatch(view, /分母为零策略/)
  assert.match(view, /v-model="form\.calculation_config\.numerator_field"/)
  assert.match(view, /v-model="form\.calculation_config\.denominator_field"/)
  assert.match(view, /v-model="form\.calculation_config\.derived_left_field"/)
  assert.match(view, /v-model="form\.calculation_config\.time_grain"/)
  assert.match(view, /v-model="form\.calculation_config\.statistical_window"/)
  assert.match(view, /v-for="\(rule, index\) in form\.calculation_config\.filters"/)
  assert.match(view, /calculation_config:\s*normalizeCalculationConfig/)
  assert.match(view, /caliberCompleteness/)
})

test("metric calculation modes expose type-matched configuration controls", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /calculation-mode-switcher/)
  assert.match(view, /calculation-mode-card/)
  assert.match(view, /currentCalculationModeMeta/)
  assert.match(view, /isCalculationModelConfigured/)
  assert.match(view, /v-if="isCalculationMode\('aggregate'\)"/)
  assert.match(view, /聚合字段/)
  assert.match(view, /v-model="form\.calculation_config\.metric_field"/)
  assert.match(view, /v-if="isCalculationMode\('ratio'\)"/)
  assert.match(view, /分子指标/)
  assert.match(view, /分母指标/)
  assert.match(view, /v-if="isCalculationMode\('derived'\)"/)
  assert.match(view, /派生运算/)
  assert.match(view, /依赖指标/)
  assert.match(view, /v-if="isCalculationMode\('window'\)"/)
  assert.match(view, /窗口函数/)
  assert.match(view, /分区字段/)
  assert.match(view, /排序字段/)
  assert.match(view, /输出别名/)
  assert.match(view, /effectiveFormula/)
  assert.doesNotMatch(view, /v-if="isCalculationMode\('custom_sql'\)"/)
  assert.doesNotMatch(view, /value:\s*"custom_sql"[\s\S]*?label:\s*"自定义 SQL"/)
})

test("metric calculation model provides dataset field candidates for editing", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /field-candidate-panel/)
  assert.match(view, /数据集字段候选项/)
  assert.match(view, /datasetFieldOptions/)
  assert.match(view, /fieldOptionGroups/)
  assert.match(view, /metricFieldOptionGroups/)
  assert.match(view, /v-for="group in metricFieldOptionGroups"/)
  assert.match(view, /class="field-picker-select"/)
  assert.doesNotMatch(view, /allow-create/)
  assert.match(view, /pickCandidateField/)
  assert.match(view, /appendExpressionField/)
  assert.match(view, /v-model="form\.calculation_config\.time_field"/)
  assert.match(view, /v-model="rule\.field"/)
})

test("trusted metric field candidates are limited to metrics from the selected dataset", () => {
  const view = read("src/views/MetricSettings.vue")
  const datasetFieldOptionsLine = view.match(/const datasetFieldOptions = computed[^\n]+/)?.[0] || ""
  const metricFieldOptionGroupsBlock = view.match(/const metricFieldOptionGroups = computed[\s\S]*?const isTimeLikeField/)?.[0] || ""
  const candidateFilterOptionsBlock = view.match(/const fieldCandidateFilterOptions = computed[\s\S]*?const filteredCandidateFields/)?.[0] || ""

  assert.match(datasetFieldOptionsLine, /metricFieldOptions\.value/)
  assert.doesNotMatch(datasetFieldOptionsLine, /dimensionFieldOptions\.value/)
  assert.match(metricFieldOptionGroupsBlock, /指标字段/)
  assert.doesNotMatch(metricFieldOptionGroupsBlock, /维度字段/)
  assert.doesNotMatch(candidateFilterOptionsBlock, /dimension/)
  assert.doesNotMatch(candidateFilterOptionsBlock, /time/)
})

test("derived trusted metrics can use existing trusted metrics as operands", () => {
  const view = read("src/views/MetricSettings.vue")
  const derivedBuilderBlock = view.match(/<div v-if="isCalculationMode\('derived'\)"[\s\S]*?<small class="builder-hint"/)?.[0] || ""

  assert.match(view, /existingTrustedMetricOptions/)
  assert.match(view, /derivedMetricOperandGroups/)
  assert.match(view, /findMetricOperand/)
  assert.match(view, /wrapDerivedMetricExpression/)
  assert.match(view, /source:\s*"trusted_metric"/)
  assert.match(view, /metric\.id !== editingId\.value/)
  assert.match(view, /已有可信指标/)
  assert.match(derivedBuilderBlock, /v-for="group in derivedMetricOperandGroups"/)
  assert.doesNotMatch(derivedBuilderBlock, /v-for="group in metricFieldOptionGroups"/)
})

test("derived metrics support advanced custom formula mode with dependency extraction", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /derived_formula_mode/)
  assert.match(view, /derived_custom_expression/)
  assert.match(view, /derivedFormulaModeOptions/)
  assert.match(view, /derivedAdvancedAggregationOptions/)
  assert.match(view, /derived-formula-mode-switcher/)
  assert.match(view, /derived-advanced-builder/)
  assert.match(view, /derived-advanced-toolbar/)
  assert.match(view, /insertDerivedExpression/)
  assert.match(view, /resolveDerivedCustomExpression/)
  assert.match(view, /extractDerivedExpressionDependencies/)
  assert.match(view, /ROUND\(SUM\(delivery_completion\) \/ COUNT\(order_id\), 2\)/)
  assert.match(view, /v-model="form\.calculation_config\.derived_custom_expression"/)
})

test("metric formula AI generation uses a conversational candidate modal", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /formulaAssistantVisible/)
  assert.match(view, /formula-assistant-dialog/)
  assert.match(view, /v-model="formulaAssistantPrompt"/)
  assert.match(view, /自然语言描述/)
  assert.match(view, /formulaCandidates/)
  assert.match(view, /候选公式/)
  assert.match(view, /formulaAssistantMessages/)
  assert.match(view, /v-model="formulaAssistantFeedback"/)
  assert.match(view, /继续修正/)
  assert.match(view, /openFormulaAssistant/)
  assert.match(view, /generateFormulaCandidate/)
  assert.match(view, /refineFormulaCandidate/)
  assert.match(view, /applyFormulaCandidate/)
  assert.match(view, /buildFormulaAssistantPayload/)
  assert.match(view, /@click="openFormulaAssistant"/)
  assert.doesNotMatch(view, /@click="generateFormula">AI 生成公式/)
})

test("metric caliber editor optimizes field discovery and formula confirmation efficiency", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /field-candidate-tools/)
  assert.match(view, /v-model="fieldCandidateKeyword"/)
  assert.match(view, /fieldCandidateRoleFilter/)
  assert.match(view, /fieldCandidateFilterOptions/)
  assert.match(view, /filteredCandidateFields/)
  assert.match(view, /公式预览/)
  assert.match(view, /formula-preview-panel/)
  assert.match(view, /formulaPreview/)
  assert.match(view, /formulaPreviewStatus/)
  assert.match(view, /applyFormulaPreview/)
  assert.match(view, /应用预览公式/)
})

test("metric caliber editor centralizes field insertion instead of repeating field strips", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /field-insert-toolbar/)
  assert.match(view, /v-model="fieldInsertTarget"/)
  assert.match(view, /fieldInsertTargetOptions/)
  assert.match(view, /insertCandidateField/)
  assert.match(view, /智能填充/)
  assert.match(view, /插入到/)
  assert.doesNotMatch(view, /field-candidate-strip/)
})

test("metric caliber editor uses controlled graphical builders instead of hardcoded formulas", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /structured-caliber-builder/)
  assert.match(view, /metric-operand-picker/)
  assert.match(view, /derived-operator-button/)
  assert.match(view, /windowFrameOptions/)
  assert.match(view, /controlledMetricExpression/)
  assert.match(view, /派生运算/)
  assert.match(view, /窗口范围/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.numerator_expression"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.denominator_expression"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.derived_expression"/)
  assert.doesNotMatch(view, /v-model="form\.calculation_config\.custom_sql"/)
  assert.doesNotMatch(view, /v-model="form\.formula"/)
  assert.doesNotMatch(view, /allow-create/)
})

test("metric dialog previews live metric data by selected dimensions", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /metric-preview-panel/)
  assert.match(view, /metric-preview-dimensions/)
  assert.match(view, /v-model="metricPreviewDimensions"/)
  assert.match(view, /metricPreviewDimensionOptions/)
  assert.match(view, /metricPreviewRows/)
  assert.match(view, /metricPreviewColumns/)
  assert.match(view, /fetchMetricPreview/)
  assert.match(view, /\/api\/metrics\/\$\{editingId\.value\}\/preview/)
  assert.match(view, /@change="handleMetricPreviewDimensionsChange"/)
  assert.match(view, /实时数据预览/)
})

test("metric preview supports ordering by field and asc/desc direction", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /v-model="metricPreviewOrderBy"/)
  assert.match(view, /v-model="metricPreviewOrderDirection"/)
  assert.match(view, /metricPreviewSortOptions/)
  assert.match(view, /默认排序（按指标）/)
  assert.match(view, /order_by: metricPreviewOrderBy\.value \|\| null/)
  assert.match(view, /order_direction: metricPreviewOrderDirection\.value/)
  assert.match(view, /<el-radio-button :value="'desc'">降序<\/el-radio-button>/)
  assert.match(view, /<el-radio-button :value="'asc'">升序<\/el-radio-button>/)
  assert.match(view, /handleMetricPreviewDimensionsChange = \(\) => /)
})

test("metric preview dimension options include derived columns from the dataset", () => {
  const view = read("src/views/MetricSettings.vue")

  assert.match(view, /const derivedColumnsJson = dataset\.derived_columns_json \|\| \{\}/)
  assert.match(view, /derivedColumnsJson\.expressions/)
  assert.match(view, /source: "dataset_derived"/)
  assert.match(view, /派生列/)
  assert.match(view, /metricPreviewDimensionOptions = computed\(\(\) => dimensionFieldOptions\.value\)/)
})
