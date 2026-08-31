---
name: fix-metric-preview-derived-columns
overview: 修复可信指标"实时数据预览"的预览维度下拉框缺少派生列的问题：前端维度候选中纳入数据集派生列，后端预览候选与 SQL 渲染支持派生列。
todos:
  - id: backend-derived-preview
    content: 修复后端 metrics.py：新增派生列解析函数，扩展 _metric_dimension_candidates 与 _metric_preview_plan 的 SQL 渲染，用 [subagent:code-explorer] 与 [skill:lsp-code-analysis] 验证引用点
    status: completed
  - id: frontend-derived-option
    content: 修复前端 MetricSettings.vue：扩展 DatasetFieldOption 类型，将 derived_columns_json 派生列加入 dimensionFieldOptions 并更新 fieldOptionLabel/fieldOptionDetail 展示
    status: completed
  - id: add-tests
    content: 补充后端 test_metric_preview.py 派生列维度预览用例及前端 biAnalysisMetricCertifier.test.mjs 静态断言
    status: completed
    dependencies:
      - backend-derived-preview
      - frontend-derived-option
  - id: run-verification
    content: 运行后端 pytest+ruff 与前端 typecheck+test:static+build 全量验证修复
    status: completed
    dependencies:
      - add-tests
---

## 需求概述

修复"可信指标编辑 → 实时数据预览 → 预览维度"下拉框中缺少数据集派生列字段的问题。

## 核心功能

- 在可信指标编辑页的"实时数据预览"预览维度多选框中，展示当前数据集已配置的派生列（`derived_columns_json.expressions` 中 `name = expression` 的 `name`）作为可选维度。
- 选中派生列维度后，实时预览请求能够被后端正确校验并执行：SQL 中派生列以计算表达式渲染（SELECT 与 GROUP BY），而非直接引用不存在的表列。
- 保持现有维度、指标字段的展示与预览行为不变，派生列与普通维度去重后共同出现在候选项中。

## 边界

- 仅影响可信指标实时数据预览的维度候选与后端预览 SQL 渲染，不改变数据集建模、指标配置等其他功能。

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2（现有 `backend/app/api/metrics.py` 既有模式）
- 前端：Vue 3 Composition API + TypeScript + Element Plus（现有 `frontend/src/views/MetricSettings.vue` 既有模式）

## 实现方案

问题有两层：前端维度候选未包含派生列；后端候选校验与 SQL 渲染不支持派生列。两端同步修复。

### 后端 backend/app/api/metrics.py

1. 新增辅助函数 `_metric_derived_columns(dataset) -> dict[str, str]`：解析 `dataset.derived_columns_json["expressions"]`（格式 `name = expression`），返回 `{name: expression}`；校验 name 符合安全标识符，表达式不含 `; -- /* */ \x00` 等危险片段。
2. 修改 `_metric_dimension_candidates`（382-402 行）：将派生列名加入候选，同时注册裸名 `name` 与带表前缀 `{table}.{name}`（与现有字段注册逻辑一致），label 用派生列名。
3. 修改 `_metric_preview_plan`（471-518 行）：渲染 selected_dimensions 时，若字段命中派生列（按 `field.split(".")[-1]` 查表），SELECT 输出 `({expr}) AS "label"`、GROUP BY 使用 `({expr})`；否则保持原 `field AS "label"` / `field` 逻辑。

### 前端 frontend/src/views/MetricSettings.vue

1. 扩展 `DatasetFieldOption.source` 类型（1541-1550 行）：增加 `"dataset_derived"`。
2. 修改 `dimensionFieldOptions`（1892-1908 行）：追加从 `dataset.derived_columns_json?.expressions` 解析的派生列选项（`{ name, label: name, type: "derived", role: "dimension", source: "dataset_derived" }`），由现有 `dedupeDatasetFields` 去重。
3. 更新 `fieldOptionLabel` / `fieldOptionDetail`（2007-2038 行）：为 `dataset_derived` 增加展示分支（如"派生列 · name"）。

### 性能与可靠性

- 派生列数量少、解析为 O(n) 线性遍历，无性能风险；计算仅发生在预览请求构建时。
- 保持与 datasets.py `_render_derived_expression` 一致的安全校验，防止 SQL 注入。
- 不引入新依赖、不改动数据结构与 API 契约，向后兼容。

## 实现注意

- `_metric_dimension_candidates` 与 `_metric_preview_plan` 仅被 metrics.py 内部调用（已确认无其他调用方），改动波及面可控。
- 派生列表达式中含 `table.column` 引用（如 `sales.amount - sales.cost`）时原样输出即可（FROM 主表），与现有数据集预览行为一致。
- 前端 value 传裸派生列名（如 `net_amount`），后端 `_safe_column_ref` 可接受，`dimension_candidates.get(field)` 可命中。

## 验证

- 后端：`cd backend && uv run pytest tests/test_metric_preview.py && uv run ruff check app/api/metrics.py`
- 前端：`cd frontend && npm run typecheck && npm run test:static && npm run build`

## Agent 扩展

### SubAgent

- **code-explorer**
- 用途：在执行前复核派生列数据流（DatasetCenter 保存 → derived_columns_json → metrics.py 解析）与前端 `dimensionFieldOptions` 的全部消费点，确认无遗漏调用方。
- 预期结果：确认改动波及面完整，无其他依赖 `dimensionFieldOptions` 或 `_metric_dimension_candidates` 的代码被遗漏。

### Skill

- **lsp-code-analysis**
- 用途：对 `_metric_dimension_candidates`、`_metric_preview_plan` 及前端派生列相关类型/函数做语义级引用与定义验证，辅助精准修改。
- 预期结果：修改后无残留引用错误，类型与调用关系一致。