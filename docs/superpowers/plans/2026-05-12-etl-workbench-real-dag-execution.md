# ETL Workbench Real DAG Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real ETL DAG executor and refactor the ETL pipeline page into a usable SmartBI workbench with node configuration, preview, monitoring, and lineage.

**Architecture:** Add a focused backend executor in `backend/app/core/etl_executor.py` and keep API orchestration in `backend/app/api/pipelines.py`. Frontend remains a single Vue view for now, using Vue Flow and Element Plus patterns already present in the repo. Existing pipeline APIs remain compatible while new preview and lineage endpoints serve the workbench.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Python unittest, Vue 3, Element Plus, Vue Flow, Node static tests.

---

### Task 1: Backend ETL Executor

**Files:**
- Create: `backend/app/core/etl_executor.py`
- Modify: `backend/app/api/pipelines.py`
- Test: `backend/tests/test_data_pipeline_execution.py`

- [ ] Write failing tests for transform mapping, filtering, derived columns, dedupe, aggregation, quality blocking, and preview without persistence.
- [ ] Implement `execute_pipeline_dag()` and `preview_pipeline_node()` with topological execution.
- [ ] Refactor `run_pipeline()` to call the executor and preserve existing audit/refresh behavior.
- [ ] Run `cd backend && uv run pytest tests/test_data_pipeline_execution.py -q`.

### Task 2: Pipeline API Contract

**Files:**
- Modify: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/api/pipelines.py`
- Test: `backend/tests/test_data_pipeline_execution.py`

- [ ] Add preview and lineage response schemas.
- [ ] Add `POST /pipelines/{pipeline_id}/preview`.
- [ ] Add `GET /pipelines/{pipeline_id}/lineage`.
- [ ] Extend DAG validation for supported transform config keys while preserving legacy DAGs.
- [ ] Run targeted backend pipeline tests.

### Task 3: Frontend ETL Workbench

**Files:**
- Modify: `frontend/src/views/DataPipelines.vue`
- Test: `frontend/tests/dataPipelinesEnterpriseEtl.test.mjs`

- [ ] Rewrite page layout into top tabs, left palette, center DAG canvas, right node config, bottom preview/monitor panels.
- [ ] Add selected node state and type-specific configuration controls.
- [ ] Add save DAG, preview selected node, run, backfill, validate, and lineage calls.
- [ ] Preserve existing create pipeline and quality-rule flows where useful.
- [ ] Run `cd frontend && npm run test:static -- dataPipelinesEnterpriseEtl.test.mjs` or the repo-supported static test command.

### Task 4: Verification and Graph Refresh

**Files:**
- Modify generated graph files under `graphify-out/` if the rebuild changes them.

- [ ] Run targeted backend tests.
- [ ] Run targeted frontend static tests.
- [ ] Run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`.
- [ ] Inspect `git status --short` and report only files changed by this task.
