---
name: fix-metric-compute-missing-join
overview: 修复"计算指标"接口 compute_metric 生成 SQL 时未渲染数据集 JOIN 子句，导致跨表指标公式报 missing FROM-clause 的 bug，并补充聚焦测试。
todos:
  - id: fix-compute-joins
    content: 修改 metrics.py 的 compute_metric，在 WHERE 处理前复用 _render_preview_joins 渲染数据集 JOIN 子句
    status: completed
  - id: add-regression-test
    content: 在 test_metric_trust_center.py 新增跨表 JOIN 指标计算回归测试，断言 SQL 含 LEFT JOIN 且返回正确值
    status: completed
    dependencies:
      - fix-compute-joins
  - id: run-verification
    content: 运行 ruff check 与 pytest 验证改动，确认无回归
    status: completed
    dependencies:
      - fix-compute-joins
      - add-regression-test
---

## 用户需求

修复"可信指标"点击"计算指标"时的 SQL 执行失败：`missing FROM-clause entry for table "order_payments"`。

## 问题定位

- 指标公式为 `SUM(order_payments.payment_value)`，引用了 `order_payments` 表；数据集主表为 `orders`，数据集已配置 `order_payments` 与 `orders` 的 JOIN 关系。
- `compute_metric`（`POST /api/metrics/{id}/compute`）生成 SQL 时只拼了 `SELECT {formula} AS _val FROM {table}`，未渲染数据集配置的 JOIN 子句，导致 `order_payments` 未进入 FROM/JOIN，PostgreSQL 报错。
- 指标"预览"接口使用了 `_render_preview_joins` 渲染 JOIN，因此预览正常、仅"计算指标"报错。

## 修复目标

- 在 `compute_metric` 中复用现有 `_render_preview_joins` 渲染数据集 JOIN 子句（置于 WHERE 过滤条件之前），使跨表公式可正常计算。
- 补充聚焦回归测试，验证带 JOIN 的跨表指标计算成功。

## 技术方案

### 修改目标

- 文件：`backend/app/api/metrics.py`
- 函数：`compute_metric`（约第 1534-1613 行，`POST /api/metrics/{metric_id}/compute`）
- 复用现有辅助函数：`_render_preview_joins(dataset, table)`（第 451-468 行），其数据来源 `_dataset_join_items` 支持 `fields_json.joins` 与 `dataset.joins_json`（dict/list/str JSON 三种形态），并内置安全校验（跳过主表自身、校验 join 类型白名单、拦截 `;`/`--`/`/*`/`*/`/`\x00`，不合法抛 400 友好错误）。

### 修复逻辑

在 `compute_metric` 生成基础 SQL（`SELECT {formula} AS _val FROM {table}` 或聚合列分支）之后、`_render_calculation_filters` 处理 WHERE 之前，追加：

```python
# 渲染数据集配置的 JOIN 子句（与指标预览逻辑保持一致），否则跨表公式会报 missing FROM-clause
join_clauses = _render_preview_joins(dataset, table)
if join_clauses:
    sql = f"{sql} {' '.join(join_clauses)}"
```

要点：

- JOIN 必须位于 WHERE 之前，因此插在 `filters_sql` 处理之前，保证 `WHERE`/`AND` 拼接逻辑不受影响。
- `_render_preview_joins` 参数 `dataset` 允许为 `None`（`_dataset_join_items` 已做空值防护），与 `compute_metric` 现有取值方式（`fields_json = (dataset.fields_json or {}) if dataset else {}`）兼容。
- Excel 数据源分支（`source_type == "excel"`，第 1576-1582 行）使用同一份 SQL 执行，同样受益，无需额外改动。
- 不改动前端（`frontend/src/views/MetricSettings.vue` 的 `computeMetric` 调用方）。

### 回归测试

- 文件：`backend/tests/test_metric_trust_center.py`，参考既有 `test_metric_lineage_uses_dataset_joins_json`（第 220-286 行）的 `_db(...)` fixture、`joins_json` 构造与 `SimpleNamespace` 用户模式。
- 用例内容：创建 datasource + dataset（主表 `orders`，`joins_json` 配置 `LEFT JOIN order_payments`，`on = orders.order_id = order_payments.order_id`），创建指标 formula=`SUM(order_payments.payment_value)`；sqlite 内存库中建 `orders`、`order_payments` 两表并插入少量数据；调用 `compute_metric`，断言返回 `last_value` 正确且 SQL 包含 `LEFT JOIN order_payments`，同时覆盖"无 JOIN 配置时行为不变"的基线断言。

### 验证步骤

1. `cd backend && uv run ruff check app/api/metrics.py tests/test_metric_trust_center.py`
2. `uv run pytest tests/test_metric_trust_center.py -q`
3. 手动验证：指标中心 → "按州统计总GMV" → 点击"计算指标"应正常返回数值，`quality_status` 置为 normal。

## 目录结构

```
backend/
├── app/
│   └── api/
│       └── metrics.py   # [MODIFY] compute_metric 中在 WHERE 处理前追加 _render_preview_joins 渲染的 JOIN 子句
└── tests/
    └── test_metric_trust_center.py  # [MODIFY] 新增跨表 JOIN 指标计算回归测试（含 orders/order_payments 双表 sqlite 用例）
```