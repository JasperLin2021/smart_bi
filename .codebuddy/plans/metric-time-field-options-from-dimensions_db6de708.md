---
name: metric-time-field-options-from-dimensions
overview: 将"编辑可信指标"中统计范围"时间字段"下拉框的候选来源从指标字段改为维度字段（含数据集已配置维度、时间维度、派生列），并移除"列出所有指标"的回退逻辑。
todos:
  - id: update-time-field-options
    content: 修改 MetricSettings.vue 的 timeFieldOptions，改为从 dimensionFieldOptions 筛选时间字段并回退到维度字段
    status: completed
  - id: add-static-test
    content: 在 biAnalysisMetricCertifier.test.mjs 补充 timeFieldOptions 数据源与回退逻辑的静态断言
    status: completed
    dependencies:
      - update-time-field-options
  - id: verify-frontend
    content: 运行 npm run typecheck 与 npm run test:static 验证改动无回归
    status: completed
    dependencies:
      - add-static-test
---

## 用户需求

在"编辑可信指标"弹窗的"统计范围"面板中，"时间字段"下拉列表当前会列出所有指标字段（当没有匹配到时间字段时回退展示全部指标），导致用户难以选择。期望该下拉列表改为从维度字段（包含数据集已配置的维度字段、时间维度，以及派生列等派生出来的字段）中筛选出具有时间含义的字段供用户选择，不再列出指标字段。

## 核心功能

- 时间字段下拉的数据来源从"指标字段"改为"维度字段"（含已配置维度、时间维度、派生列）
- 仅展示具有时间含义的字段（依据字段名/标签/类型中的时间语义关键词判定）
- 无匹配结果时回退展示全部维度字段，保证下拉列表非空且不再是指标列表
- 保持已保存指标的 time_field 值可正常显示与重新选择

## 技术栈

- 现有项目，沿用 Vue 3 Composition API + TypeScript + Element Plus，仅修改前端单文件
- 后端 `backend/app/core/metric_binding.py` 的 `_metric_time_field` 仅消费已保存的 `time_field` 值，不依赖下拉选项来源，无需改动

## 实现方案

将 `frontend/src/views/MetricSettings.vue` 中 `timeFieldOptions` 计算属性的数据源由 `datasetFieldOptions`（仅指标字段，`metricFieldOptions` 的别名）切换为 `dimensionFieldOptions`（维度字段）。

`dimensionFieldOptions`（第 1975-2006 行）已完整覆盖用户诉求中的两类字段来源：

- 已选择的字段：`fields_json.dimensions`、`fields_json.fields` 中非指标字段（legacy）、`semantic_model_json.dimensions`、`semantic_model_json.time_dimensions`
- 派生出来的字段：`derived_columns_json.expressions` 解析出的派生列（`source: "dataset_derived"`，`type: "derived"`）

修改逻辑：

```ts
const timeFieldOptions = computed(() => {
  // 从维度字段（含数据集已配置维度、时间维度、派生列）中筛选时间含义字段，不再回退到指标列表
  const matches = dimensionFieldOptions.value.filter(isTimeLikeField)
  return matches.length ? matches : dimensionFieldOptions.value
})
```

关键决策与取舍：

- `isTimeLikeField` 正则（匹配 date/time/日期/时间/day/month/year/created/updated/biz_date 等）保持不变，可覆盖时间维度与派生列字段名
- 无匹配时回退到"全部维度字段"而非"全部指标字段"，既保证下拉非空、便于用户兜底选择，又满足"不列出所有指标"的核心诉求
- 派生列字段 type 为 "derived"，字段名含时间关键词时同样能被筛选，展示时通过现有 `fieldOptionLabel`/`fieldOptionDetail` 标注"派生列"，无需新增 UI 逻辑

性能：`timeFieldOptions` 为响应式计算属性，仅做一次 O(n) 过滤，维度字段规模有限，无性能瓶颈；改动仅影响该下拉的选项来源，不涉及数据流与保存逻辑，爆炸半径可控。

## 目录结构

```
frontend/
├── src/
│   └── views/
│       └── MetricSettings.vue   # [MODIFY] 将 timeFieldOptions 数据源由 datasetFieldOptions（指标）改为 dimensionFieldOptions（维度），无匹配时回退到维度字段
└── tests/
    └── biAnalysisMetricCertifier.test.mjs  # [MODIFY] 补充 timeFieldOptions 静态断言，防止回归（数据源为 dimensionFieldOptions、回退不再引用指标字段）
```

## 验证

- `cd frontend && npm run typecheck`：确认类型无误
- `npm run test:static`：确认既有断言与新增断言全部通过（现有第 110-122 行断言只针对 datasetFieldOptions 与 fieldCandidateFilterOptions，不受影响）