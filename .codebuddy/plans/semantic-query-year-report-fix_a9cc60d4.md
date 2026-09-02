---
name: semantic-query-year-report-fix
overview: 修复 AI 报表语义查询链路：过滤器类型（filters 支持字符串与字典）、时间维度按年/月聚合（开放派生粒度维度）、多表 JOIN（orders×customers×order_payments），使"2017年销售经营分析报表"等按年度/时间过滤的请求可正确执行。
todos:
  - id: backend-filters-time
    content: 修改 schemas/query.py filters 支持字符串，并在 semantic_layer.py 实现 dialect 检测、时间粒度表达式与派生时间维度(year/month)幂等展开及大小写回退解析
    status: completed
  - id: backend-join
    content: 在 semantic_layer.py 增加 joins_json 解析渲染(兼容 on/left-right/字符串格式)与跨表引用校验，build_semantic_query_plan 输出 FROM+JOIN
    status: completed
    dependencies:
      - backend-filters-time
  - id: backend-api-wiring
    content: 接线 query.py 向 build 传入 datasource，datasets.py 的 semantic-model 返回展开模型，并用 [skill:lsp-code-analysis] 核查所有调用点
    status: completed
    dependencies:
      - backend-join
  - id: agent-tools
    content: 更新 agent/src/tools.ts：get_dataset_schema 合并 semantic-model 端点返回，query_dataset 描述补充时间过滤与 _year/_month 维度用法
    status: completed
    dependencies:
      - backend-api-wiring
  - id: tests-verify
    content: 扩展 test_semantic_layer.py 覆盖 filters 字符串、时间粒度聚合、JOIN 跨表与大小写回退，运行 pytest+ruff 及 agent build+smoke 验证
    status: completed
    dependencies:
      - agent-tools
---

## 用户需求

用户通过对话式 AI 报表 Agent 提问"2017年销售经营分析报表"后，Agent 未能产出按 2017 年度口径的报表，而是降级展示了全量订单数据，并披露了三条根因。用户要求分析原因并修复。

## 根因定位（已通过代码核实）

1. **filters 类型契约不一致（422 直接原因）**：Agent 工具层 `query_dataset` 将 `filters` 定义为字符串数组，LLM 生成 `["order_date >= '2017-01-01'"]`；而后端 `SemanticQueryRequest.filters` 声明为 `List[Dict[str, Any]]`，Pydantic 校验字符串必然失败并返回 422。后端 `_render_filter` 其实早已兼容字符串格式，属 schema 与实现脱节。
2. **时间维度无法按年/月聚合**：语义层 `build_semantic_query_plan` 对时间维度与普通维度同样按原始列 SELECT/GROUP BY，`granularity` 从不参与 SQL 生成；语义模型只开放了字段本身（或根本没有时间维度），未暴露按年/月派生的维度 ID，LLM 请求派生字段（如 `Datetime` 相关年月维度）即报"维度不存在"；且维度 ID 匹配为大小写敏感，放大了误报。
3. **跨表 JOIN 缺失**：语义层 SQL 仅生成 `FROM {主表}`，从不消费 `joins_json`；当指标/维度引用 `customers.xxx`、`order_payments.xxx` 时数据库报"缺失 FROM 表条目/无此列"错误。此外实际存储的 join 条目是 `{"type":"LEFT JOIN","right":"customers","on":"orders.customer_id = customers.customer_id"}` 形式，现有解析器只识别 `left/right/op` 字段，即使接入也会静默跳过。

## 修复目标

- 修复后 Agent 可通过字符串过滤器按 `2017-01-01 ~ 2017-12-31` 精确限定时间范围（不再 422）；
- 语义模型对时间字段开放 day/year/month 三种粒度维度（如 `order_date_year`/`order_date_month`），Agent 可按年/月分组取数；
- 关联数据集（orders × customers × order_payments）查询自动带上配置的 JOIN，跨表金额/维度取数正常；
- 补回归测试，确保语义查询链路可用且不破坏 RLS、数据集预览等既有能力。

## 技术栈

沿用现有架构，仅做后端 Python（FastAPI + Pydantic + SQLAlchemy，`uv` 管理）与 Agent（TypeScript，pi-agent-core）的局部修复，无新增依赖、无数据库迁移。

## 根因与修复对照

| 错误现象 | 根因文件 | 修复 |
| --- | --- | --- |
| filters 任意过滤返回 422 | `backend/app/schemas/query.py` | `filters` 类型放宽为 `List[Union[str, Dict[str, Any]]]`，与 `_render_filter` 既有双格式能力对齐 |
| 无法按月/年聚合、"维度不存在" | `backend/app/core/semantic_layer.py` | 消费 `granularity` 生成方言感知的时间表达式；幂等展开派生时间维度；维度 ID 大小写不敏感回退解析 |
| 跨表取数报缺失 FROM | `backend/app/core/semantic_layer.py` | 读取 `joins_json` 并兼容三种存储格式渲染 JOIN；跨表引用校验给出明确错误 |
| Agent 看不到可用的时间维度 | `agent/src/tools.ts`、`backend/app/api/datasets.py` | `get_dataset_schema` 额外拉取 semantic-model 端点；该端点返回含派生时间维度的展开模型 |


## 实施方案

### 1. filters 契约对齐

- `backend/app/schemas/query.py`：`SemanticQueryRequest.filters` 改为 `List[Union[str, Dict[str, Any]]] = []`（补 `Union` 导入）。
- 字符串格式沿用现有 `FILTER_RE`：`order_date >= 2017-01-01`、`status = paid`；dict 格式沿用 `id/field/column + operator/op + value`。不做行为变更。

### 2. 时间粒度与派生时间维度（semantic_layer.py）

- 新增 dialect 检测：`source_type == "excel"` → `duckdb`；否则按 `database_url` 前缀识别 `sqlite / mysql / postgresql`（doris 走 mysql 语法兼容分支）；未知时用 SQLAlchemy `engine.dialect.name` 兜底。
- 新增时间表达式渲染（year/month，输出文本便于展示）：
- sqlite：`strftime('%Y'/'%Y-%m', col)`
- duckdb：`strftime(col, '%Y'/'%Y-%m')`（注意参数顺序与 sqlite 相反）
- mysql/doris：`DATE_FORMAT(col, '%Y'/'%Y-%m')`
- postgresql：`to_char(col, 'YYYY'/'YYYY-MM')`
- 新增幂等展开函数 `expand_time_dimensions(model)`：为每个时间维度追加 `<id>_year`、`<id>_month` 派生条目（granularity 分别为 year/month），已存在则跳过；label 追加"年份/月份"。仅在读取/构建出口调用（`infer_semantic_model` 结果之上），不改 `normalize_semantic_model` 的存储语义，不落库。
- `build_semantic_query_plan` 的维度解析增加大小写不敏感回退与"id 命中 time_dimension 派生后缀"解析；未命中时错误信息列出可用维度 ID 提示（缓解 `Datetime` 类误报）。
- `infer_semantic_model`（无 semantic_model_json 的字段推断路径）：按时间提示词（datetime/date/time/dt/ymd 等，参考 `dataset_ai_config.TIME_HINTS`）把时间列归入 time_dimensions，使其可获得派生粒度。

### 3. JOIN 渲染（semantic_layer.py）

- 新增 `_join_sql_parts(dataset, default_table)`，兼容三类存储格式并归一为 `JOIN 子句`：

1. dict `{"type","left","right","op"}`（现有 UI 格式）；
2. dict `{"type","right"|"table","on"|"join_on"}`（实际存储/mock_data.sql 格式，`on` 为 `t1.c1 op t2.c2`）；
3. 字符串 `LEFT JOIN t1.c1 = t2.c2` 或带 `ON` 的完整子句。

- JOIN 类型白名单（JOIN/LEFT/RIGHT/INNER/FULL JOIN）、表名/列名/`on` 条件正则白名单校验，防注入；join 表取"非主表一侧"。
- 收集 FROM+JOIN 的表集合，校验 SELECT/WHERE 中出现的限定表引用均在该集合内，否则抛出带修复提示的 `ValueError`（如"字段 customers.region 引用了未关联的表，请检查数据集关联配置"）。
- `FROM 主表` 之后按序追加 join 子句，其余 SELECT/GROUP BY/ORDER BY/LIMIT/RLS 注入逻辑保持不变。

### 4. API 接线与 Agent 侧

- `backend/app/api/query.py`：`semantic_query` 处 `build_semantic_query_plan(dataset, payload, datasource=datasource)` 传入 dialect 来源。
- `backend/app/api/datasets.py`：`get_dataset_semantic_model` 返回 `expand_time_dimensions(infer_semantic_model(dataset))`（幂等，供 Agent 与前端只读展示）。
- `agent/src/tools.ts`：
- `get_dataset_schema` 改为并发拉取 `GET /api/datasets/{id}` 与 `GET /api/datasets/{id}/semantic-model`，合并为 `{dataset, semantic_model}` 返回，使 LLM 可见 `_year`/`_month` 派生时间维度与 joins 字段；
- `query_dataset.filters` 描述补充：支持字符串 `"order_date >= 2017-01-01"` 与 `"order_date < 2018-01-01"` 成对限定区间、支持 `=`/`!=`/`>`/`>=`/`<`/`<=`/`LIKE`；dimensions 说明提示可用 `<时间维度id>_year`、`<时间维度id>_month` 做年/月聚合。

## 目录结构与改动清单

```
backend/
├── app/
│   ├── schemas/query.py            # [MODIFY] filters: List[Union[str, Dict[str, Any]]]
│   ├── core/semantic_layer.py      # [MODIFY] dialect 检测、时间表达式、expand_time_dimensions、
│   │                               #          大小写回退解析、_join_sql_parts、build plan 渲染 JOIN/时间粒度
│   ├── api/query.py                # [MODIFY] semantic_query 传 datasource 给 build_semantic_query_plan
│   └── api/datasets.py             # [MODIFY] get_dataset_semantic_model 返回展开后的模型（幂等）
│   └── core/dataset_ai_config.py   # [MODIFY](可选) AI 建议模型时间维度补充 month/year 派生条目
└── tests/
    └── test_semantic_layer.py      # [MODIFY] 新增 filters 字符串、时间粒度、JOIN、大小写回退测试
agent/
└── src/
    ├── tools.ts                    # [MODIFY] get_dataset_schema 合并 semantic-model；query_dataset 描述
    └── agent.ts                    # [MODIFY](可选) SYSTEM_PROMPT 补充时间过滤与派生维度使用指引
```

## 测试与验证

- 后端：`cd backend && uv run pytest backend/tests/test_semantic_layer.py && uv run ruff check .`；新增用例：

1. `SemanticQueryRequest(filters=["sales.status = paid", "sales.amount >= 50"])` 构造与执行通过（schema 修复回归）；
2. 含时间维度 fixture（sales.order_date）请求 `order_date_year`/`order_date_month`：断言 SQL 含方言时间函数、执行结果按月/年正确分组；大小写变体 `ORDER_DATE_YEAR` 可回退命中；
3. orders/customers/order_payments 三表 sqlite fixture，`joins_json` 用 `on` 形式存储：跨表按 `customers.region` + 年聚合金额执行成功且 SQL 含 JOIN；
4. 引用未关联表字段时返回清晰 ValueError（不产生非法 SQL）。

- Agent：`cd agent && npm run build && node test/smoke.mjs`，确认工具描述变更不影响 SSE 链路与转发契约。
- 回归关注点：RLS 注入在 plan 生成之后执行，本改动不触碰其流程；`get_dataset`/DatasetOut 序列化不变；不新增数据库迁移；Excel(DuckDB) 与 SQL 数据源均按 dialect 分支验证。

## 风险与边界

- 时间函数按 dialect 生成，仅覆盖 sqlite/duckdb/mysql(含 doris 语法兼容)/postgresql；未知方言回退为原列聚合并给出告警性错误，避免生成非法 SQL。
- 派生时间维度仅在查询构建与 schema 读取出口展开、幂等、不写库；若前端编辑页回显并保存展开模型，条目会被原样持久化（合法无害，normalize 已接受任意 granularity）。
- 本修复不改变既有数据集结构、不引入破坏性行为，Agent 历史会话的降级说明将随修复自然消失。

## Agent 扩展

### Skill

- **lsp-code-analysis**
- 用途：在后端语义层与 API 改动完成后，用 LSP 语义工具核查 `build_semantic_query_plan`、`infer_semantic_model`、`get_dataset_semantic_model` 的全部调用点与引用，确认签名适配且无遗漏（覆盖 api/query.py、api/datasets.py、dataset_ai_config.py、tests）。
- 预期结果：无遗留的旧签名调用，类型/引用检查通过，改动影响面收敛。