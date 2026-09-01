---
name: 修复可信指标实时预览未使用输出别名
overview: 修复可信指标编辑中的"实时数据预览"忽略 calculation_config.output_alias（输出别名）的问题：预览 SQL 列名、metric_column、排序逻辑与前端排序选项均改为优先使用输出别名，缺失时回退到指标名称，并补充测试。
todos:
  - id: backend-preview-alias
    content: 修改 _metric_preview_plan 优先使用 calculation_config.output_alias，空则回退 metric.name
    status: completed
  - id: backend-orderby-compat
    content: 修改 _metric_preview_order_by 兼容旧请求 metric.name 排序，ORDER BY 统一使用输出别名
    status: completed
    dependencies:
      - backend-preview-alias
  - id: frontend-sort-options
    content: 修改 MetricSettings.vue 的 metricPreviewSortOptions，指标排序 value 同步为输出别名
    status: completed
    dependencies:
      - backend-preview-alias
  - id: preview-alias-tests
    content: 在 test_metric_preview.py 新增输出别名生效与旧排序兼容用例，保留回退断言
    status: completed
    dependencies:
      - backend-preview-alias
      - backend-orderby-compat
  - id: verify-changes
    content: 运行 pytest + ruff（backend）与 typecheck + test:static（frontend）验证改动
    status: completed
    dependencies:
      - frontend-sort-options
      - preview-alias-tests
---

## 问题确认

是的，这是一个 bug。用户在「可信指标」编辑页的派生指标等计算模式中配置了「输出别名」（`calculation_config.output_alias`，如 `gross_margin_rate`），但「实时数据预览」的指标列表头显示的是指标名称（`metric.name`）而非输出别名，两者不一致。

## 功能预期

- 「实时数据预览」中指标列应优先使用已配置的「输出别名」作为字段名（表头、SQL 输出列、排序字段均一致）
- 未配置输出别名时，保持现有行为（回退使用指标名称），不破坏已有数据与请求
- 排序（ORDER BY）在升级前后均可用：新请求可用输出别名，旧请求仍可传指标名称，不产生 400 报错

## 核心改动点

1. 后端预览计划：读取 `calculation_config.output_alias` 作为指标列别名，空则回退 `metric.name`
2. 后端排序校验：兼容旧请求传 `metric.name` 的排序值
3. 前端排序选项：指标排序 value 同步为输出别名（非空时）
4. 补充聚焦测试，验证输出别名生效与回退行为

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy（复用 `backend/app/api/metrics.py` 既有模式）
- 前端：Vue 3 Composition API + TypeScript（复用 `frontend/src/views/MetricSettings.vue` 既有模式）
- 测试：unittest（`backend/tests/test_metric_preview.py`）

## 实现方案

### 后端（backend/app/api/metrics.py）

1. `_metric_preview_plan()`（约第 568 行）：

- 读取 `config = _calculation_config(metric)`，取 `output_alias = str(config.get("output_alias") or "").strip()`
- `metric_alias = _metric_preview_alias(output_alias or metric.name)`，其余 SQL 组装逻辑不变（SELECT AS、GROUP BY 无关、ORDER BY、返回的 `metric_column` 全部跟随 metric_alias）
- `output_alias` 复用 `_metric_preview_alias()` 的合法性校验（非空、≤128、禁注入 token），空值自然回退指标名，安全性不降级

2. `_metric_preview_order_by()`（约第 532-552 行）：

- 增加参数 `metric_name: str | None = None` 传入 `metric.name`
- 排序匹配条件改为 `order_by == metric_alias or (metric_name and order_by == metric_name)`，命中的 ORDER BY 统一输出 `_quote_alias(metric_alias)`，保证旧请求（按指标名排序）不因升级返回 400，且排序列与输出列别名一致

### 前端（frontend/src/views/MetricSettings.vue）

3. `metricPreviewSortOptions`（约第 2010-2022 行）：

- 指标排序项 value 由 `metricName` 改为 `outputAlias || metricName`（`outputAlias` 取 `editingMetric.calculation_config.output_alias` 并 trim）
- 更新注释说明：优先输出别名、回退指标名，与后端 metric_column 保持一致
- 表头渲染（第 858-868 行）无需改动，直接展示后端返回列名

### 测试（backend/tests/test_metric_preview.py）

4. 新增用例：

- 设置 `calculation_config.output_alias = "gross_margin_rate"`，断言 `result["columns"]` 指标列名为输出别名、`query.metric_column` 为别名、SQL 含 `AS "gross_margin_rate"`、默认 ORDER BY 为别名
- 兼容用例：请求 `order_by=metric.name`（旧值）仍返回 200 且 ORDER BY 落到别名列
- 保留现有无 `output_alias` 用例，验证回退指标名行为不受影响（第 113 行断言不变）

### 关键决策与取舍

- 采用「输出别名优先、指标名回退」而非强制别名：指标名是唯一约束且为既有下游约定（派生公式引用、绑定校验），强制替换风险高；回退保证存量指标行为零变化
- ORDER BY 兼容双值：避免前端缓存/旧请求在升级后出现「排序字段不合法」的回归，改动面最小
- 不修改 Metric 模型与数据库结构：`output_alias` 已存于 `calculation_config` JSON，无需迁移
- 边界情况：输出别名为空/非法时回退指标名；别名与维度标签重名属用户配置问题，本修复不额外处理

## 实施注意

- 改动聚焦于 metrics.py 两个函数与 MetricSettings.vue 一个 computed，不触碰其他预览/查询链路
- `_metric_preview_alias()` 已包含 SQL 注入防护，新增的 output_alias 取值必须经由该校验后再拼 SQL
- 验证命令：后端 `uv run pytest backend/tests/test_metric_preview.py` + `uv run ruff check backend/app/api/metrics.py backend/tests/test_metric_preview.py`；前端 `npm run typecheck` + `npm run test:static`