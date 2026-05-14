# ETL Workbench Real DAG Execution Design

## Goal

Refactor the ETL pipeline module into a real in-app ETL workbench: users can design a pipeline visually, configure nodes, preview intermediate data, run a deterministic DAG, inspect quality and lineage impact, and deliver data into BI datasets.

## Scope

This change covers both backend and frontend. The backend must execute the DAG semantics instead of treating `dag_json` as display metadata only. The frontend should follow the supplied SmartBI reference: left node/source palette, central DAG canvas, right node configuration, bottom data preview and monitoring, and tabs for design, preview, schedule, monitor, and lineage.

The first production-ready version should stay bounded. It will not introduce Airflow, Prefect, dbt, or a new scheduler dependency. It will use an in-process row-set executor backed by existing dataset extraction and quality-rule logic.

## Backend Architecture

Add a focused ETL execution layer under `backend/app/core/etl_executor.py`. `backend/app/api/pipelines.py` remains responsible for permissions, validation, API shape, audit logging, and persistence, while the executor owns node ordering and row-set transformations.

The executor accepts a `DataPipeline`, target `Dataset`, `DataSource`, active quality rules, and `PipelineRunRequest`. It returns a structured result with final columns, final rows, node logs, quality results, and load statistics.

Node execution is topological and deterministic:

- `source` / `extract`: reuse the existing dataset SQL extraction helpers.
- `transform`: apply mapping, type conversion, filters, derived columns, dedupe, and aggregation to the upstream row set.
- `quality`: evaluate active quality rules against the current row set and optionally block downstream load.
- `load` / `sink`: update dataset refresh state and, when configured, write rows to a target table.

The DAG remains stored in `DataPipeline.dag_json`, but nodes get a stable config contract. Pipeline-level configuration may add small fields for workbench behavior and compatibility, but the preferred path is to keep most workflow semantics inside versioned `dag_json`.

## DAG Contract

Each node should support this shape:

```json
{
  "id": "normalize_order",
  "type": "transform",
  "label": "标准化字段",
  "position": { "x": 360, "y": 120 },
  "config": {
    "field_mapping": [{ "source": "order_id", "target": "订单ID" }],
    "type_conversions": [{ "field": "amount", "type": "decimal" }],
    "filters": [{ "field": "status", "operator": "in", "value": ["PAID", "COMPLETE"] }],
    "derived_columns": [{ "name": "net_amount", "expression": "amount - discount" }],
    "dedupe": { "keys": ["order_id"], "keep": "first" },
    "aggregations": {
      "group_by": ["create_date"],
      "metrics": [{ "field": "amount", "function": "sum", "alias": "gmv" }]
    }
  }
}
```

For compatibility, legacy nodes with only `id`, `type`, and `label` remain valid and execute as pass-through for transform/load semantics where needed.

## API Changes

Keep current endpoints and add workbench-specific endpoints:

- `POST /api/pipelines/{pipeline_id}/preview`: run the same executor to a selected node with a row limit and no persistence.
- `GET /api/pipelines/{pipeline_id}/lineage`: return source table, transform nodes, quality nodes, and target dataset/table impact.

Enhance existing responses so frontend can consume node-level logs from `DataPipelineRun.node_logs_json` without custom parsing. Existing `/run`, `/validate`, `/runs`, and `/quality-rules` endpoints stay compatible.

## Frontend Design

Refactor `frontend/src/views/DataPipelines.vue` into an ETL workbench:

- Top tabs: flow design, preview data, schedule, monitor, lineage.
- Left palette: data sources and reusable node types.
- Center canvas: Vue Flow DAG with status, record counts, and validation markers.
- Right panel: selected node configuration with type-specific controls.
- Bottom section: data preview, quality results, execution logs, and run metrics.

The frontend should support saving the whole DAG, selecting nodes, editing node config, previewing the selected node, running the whole pipeline, and viewing lineage impact. Drag affordances can exist, but first implementation may add nodes via buttons/templates to keep behavior stable.

## Testing

Backend tests should cover:

- transform node mapping, type conversion, filtering, derived fields, dedupe, and aggregation.
- quality node blocking and warning behavior.
- load node refresh statistics and optional target-table writing.
- preview-to-node without persistence.
- lineage endpoint shape.

Frontend tests should assert the workbench structure, node configuration controls, preview/run/lineage API calls, and the absence of marketing-style hero sections.

## Constraints

The repository currently has a dirty worktree with many unrelated changes. Implementation must avoid reverting unrelated files and keep changes focused on ETL pipeline backend/frontend files and tests.
