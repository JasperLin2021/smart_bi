---
name: metric-filter-include-dimensions
overview: 扩展指标设置页过滤/分区/排序字段下拉选项，使其同时包含维度字段与指标字段。
todos:
  - id: extend-field-option-groups
    content: 扩展 MetricSettings.vue 的 fieldOptionGroups 以包含维度字段分组
    status: completed
  - id: run-frontend-static-tests
    content: 运行前端静态测试验证既有检查通过
    status: completed
    dependencies:
      - extend-field-option-groups
  - id: run-frontend-typecheck
    content: 运行前端类型检查确保无类型错误
    status: completed
    dependencies:
      - extend-field-option-groups
---

## 产品概述

在“编辑可信指标”页面的“计算口径”标签页中，用户配置指标过滤/排除规则时，需要通过下拉框选择过滤字段。当前下拉框仅展示指标字段，无法选择维度字段（如地区、渠道、状态、时间等），导致常见的按维度口径过滤场景无法直接配置。

## 核心功能

- “过滤/排除规则”中的“选择过滤字段”下拉框需同时展示维度字段和指标字段
- 维度字段与指标字段分组展示，保持界面清晰
- 窗口函数模式的“分区字段”和“排序字段”共用同一选项分组，扩展后也会同时展示维度字段（业务上合理，如按日期/地区分区、排序）
- 后端渲染过滤 SQL 时已不区分字段类型，无需后端改动

## Tech Stack Selection

- 前端：Vue 3 + TypeScript + Element Plus（沿用项目现有技术栈）
- 仅涉及前端视图层修改，后端无需调整

## Implementation Approach

### 方案说明

修改 `frontend/src/views/MetricSettings.vue` 中的 `fieldOptionGroups` 计算属性。该属性当前只返回“指标字段”分组，并被过滤规则、窗口函数分区字段、窗口函数排序字段三个下拉框共用。将其扩展为同时返回“维度字段”和“指标字段”两个分组，即可让过滤字段下拉框支持维度选择，同时让分区/排序字段也能选择维度，符合 BI 口径配置习惯。

### 关键决策

- **复用 `fieldOptionGroups` 而非新建属性**：分区字段、排序字段、过滤字段在业务上都可能需要维度字段，统一扩展比单独为过滤字段建属性更简洁，也避免维护多份相似分组逻辑。
- **保持 `metricFieldOptionGroups` 不变**：指标字段选择、分子/分母字段、窗口函数基础表达式等位置仍应只选指标，因此单独保留该属性。
- **后端无需改动**：`_render_calculation_filters` 仅校验字段名合法性与操作符，不限制字段语义类型，维度字段名同样可通过 `_safe_column_ref` 校验。

### 性能与可靠性

- 仅改动一个计算属性，时间复杂度与字段数量线性相关，无额外 I/O。
- `dedupeDatasetFields` 已用于字段去重，扩展分组后不会引入重复选项。
- 前端静态测试与类型检查可验证模板引用和类型一致性。

## Implementation Notes

- 修改位置：`frontend/src/views/MetricSettings.vue` 第 1936–1938 行附近的 `fieldOptionGroups`。
- 将 `{ label: "指标字段", options: metricFieldOptions.value }` 扩展为包含 `{ label: "维度字段", options: dimensionFieldOptions.value }` 和 `{ label: "指标字段", options: metricFieldOptions.value }` 两个分组，并过滤空分组。
- `dimensionFieldOptions` 已在同一文件中定义，直接复用。
- 检查 `fieldOptionLabel(field)` 和 `fieldOptionDetail(field)` 对维度字段的展示是否一致（当前实现对所有 DatasetFieldOption 类型通用）。
- 无需新增测试断言，但需运行现有前端静态测试确保不破坏既有检查。
- 注意保留空分组过滤逻辑，避免维度或指标为空时出现空分组。

## Architecture Design

本次修改为前端视图层局部调整，不涉及架构变更。数据流保持不变：

用户选择过滤字段 → `form.calculation_config.filters` 更新 → 保存时随指标配置提交到后端 → 后端 `_render_calculation_filters` 渲染为 SQL WHERE 条件。

## Directory Structure

```
e:/smart_bi/
└── frontend/
    └── src/
        └── views/
            └── MetricSettings.vue   # [MODIFY] 扩展 fieldOptionGroups 计算属性，使过滤/分区/排序字段下拉框同时支持维度字段和指标字段
```

## Key Code Structures

无需新增接口或类型。相关类型 `DatasetFieldOption` 与工具函数 `dedupeDatasetFields`、`fieldOptionLabel`、`fieldOptionDetail` 已在当前文件中定义并复用。