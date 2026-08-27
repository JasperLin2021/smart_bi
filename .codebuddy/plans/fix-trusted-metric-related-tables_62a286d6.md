---
name: fix-trusted-metric-related-tables
overview: 修复"编辑可信指标"中选择数据集后只能读取主表字段的问题，让语义模型与字段候选区包含主表及关联表的完整 join 字段。
todos:
  - id: fix-role-index
    content: 修复 DatasetCenter.vue 中 syncFieldRoleConfigs 的 role 建议 index 为每表独立计数
    status: completed
  - id: fix-old-dataset-backfill
    content: 修复 DatasetCenter.vue 中 applySavedFieldModel 对关联表字段按建议 role 补齐
    status: completed
    dependencies:
      - fix-role-index
  - id: fix-metric-candidates
    content: 修复 MetricSettings.vue 字段候选面板展示维度+指标全部字段并扩展筛选 tab
    status: completed
  - id: verify-fix
    content: 运行前端 typecheck/build 并验证可信指标字段候选展示完整数据
    status: completed
    dependencies:
      - fix-role-index
      - fix-old-dataset-backfill
      - fix-metric-candidates
---

## 用户需求

在"编辑可信指标"对话框的"基本信息 → 选择数据集"后，字段候选项只能获取主表数据，缺少关联表（带 Join 关系）的完整数据。期望读取主表及关联表的完整字段。

## 问题现象

- 可信指标编辑页的"数据集字段候选项"面板只显示主表（如 `order_payments`）字段，关联表（如 `orders`）字段不出现。
- 字段类型筛选 tab 只有"全部指标 / 指标"，无维度选项。

## 根因

1. **DatasetCenter.vue 的 role 建议 index 跨表累计**：`syncFieldRoleConfigs` 用全局递增 index 传给 `suggestedRoleForColumn`（index >= 12 返回 "ignore"）。主表字段数 >= 12 时，关联表所有字段 index 均 >= 13，全部被建议为 "ignore"，导致保存的 `semantic_model_json` / `fields_json` / `aggregations_json` 只含主表字段。
2. **MetricSettings.vue 字段候选只读指标**：`datasetFieldOptions = metricFieldOptions` 仅读取指标类字段，即使语义模型包含关联表维度字段也不会展示。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus（复用现有项目技术栈，不引入新依赖）
- 修改文件：`frontend/src/views/DatasetCenter.vue`、`frontend/src/views/MetricSettings.vue`

## 实现方案

### 修复 1：DatasetCenter.vue —— role 建议 index 改为每表独立计数

`syncFieldRoleConfigs`（约行 1880-1904）中，将跨表累计的 `globalIndex` 改为在 `tables.forEach` 内部从 0 开始的 `tableIndex`，使主表和每个关联表各自前 12 个字段都能获得建议 role（dimension/metric），关联表字段得以进入 `dimensionConfigs`/`metricConfigs`，保存后 `semantic_model_json` 等 JSON 即包含关联表字段。

### 修复 2：DatasetCenter.vue —— 旧数据集加载时补齐关联表字段 role

`applySavedFieldModel`（行 1939-1967）回填保存记录后，对 role 仍为 "ignore" 且属于关联表（`config.table !== form.table`）的字段，按表内 index 调用 `suggestedRoleForColumn` 建议 role。主表字段保持严格按保存状态回填（不影响既有行为）。这样旧数据集在 DatasetCenter 重新打开并保存后，语义模型即含关联表字段，无需手动逐个改 role。

### 修复 3：MetricSettings.vue —— 字段候选面板展示主表+关联表全部字段

- 扩展 `FieldCandidateRoleFilter` 类型为 `"all" | "dimension" | "metric"`（行 1387）。
- 新增 `allDatasetFieldOptions = dedupeDatasetFields([...dimensionFieldOptions, ...metricFieldOptions])`，合并维度与指标字段（行 1901 附近）。
- `fieldCandidateFilterOptions`（行 1917-1920）改为"全部字段 / 维度 / 指标"三项，count 基于 allDatasetFieldOptions。
- `filteredCandidateFields`（行 1921-1928）基于 allDatasetFieldOptions，支持 `role === "dimension" | "metric"` 匹配。
- 模板（行 347、368、393）中字段候选面板的 `datasetFieldOptions.length` 判断改为 `allDatasetFieldOptions.length`，空态文案由"暂无指标候选"改为"暂无字段候选"。
- `datasetFieldOptions` 本身保留指标语义，供 `timeFieldOptions`、公式助手、`findDatasetField`、derived operands 等既有逻辑继续使用，降低影响面。

## 性能与影响面

- 全部为 computed 派生逻辑，依赖数据量小（单数据集字段数），无性能瓶颈；`dedupeDatasetFields` 保持 O(n)。
- 改动限定在字段 role 建议与可信指标字段候选展示，不触碰数据存储、API、保存链路。
- 修复 1+2 保证新/旧数据集重新保存后 `semantic_model_json` 均包含关联表字段；修复 3 保证可信指标面板展示完整字段。

## 验证

- 运行 `cd frontend && npm run typecheck` 与 `npm run build` 确认无类型/构建错误。
- 浏览器验证：DatasetCenter 编辑含关联表的数据集 → 保存 → 打开可信指标编辑 → 选择该数据集 → 字段候选面板出现主表+关联表字段，筛选 tab 含"维度/指标"。