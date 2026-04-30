# Trusted BI Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing BI prototype into a trust-centered operating BI product, starting by merging "可信指标中心" into the current metric configuration page.

**Architecture:** Build trust metadata into the existing metric domain first, then expose it through catalog, smart query, dashboards, alerts, and decision workflows. Keep the current Vue + FastAPI structure and avoid introducing a parallel metric product surface.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Vue 3, Pinia, Element Plus, pytest, Vite.

---

## Batch Map

### P0: Trusted Metric Center

**Files:**
- Modify: `backend/app/models/metric.py`
- Modify: `backend/app/schemas/metric.py`
- Modify: `backend/app/api/metrics.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/20260430_0009_metric_trust_center.py`
- Create: `backend/tests/test_metric_trust_center.py`
- Modify: `frontend/src/views/MetricSettings.vue`

- [x] Write failing tests for trust fields, certification status, lineage output, catalog metadata sync, and org-scoped metric visibility.
- [x] Add metric trust columns: certification status, certifier, certification time, caliber version, data update time, quality status, quality message, lineage JSON.
- [x] Validate certification and quality states in create/update.
- [x] Add metric lineage API.
- [x] Merge trusted metric UX into the existing metric page.
- [x] Verify with targeted tests, full backend tests, and frontend build.

### P1: Trust Signals Across Consumption Surfaces

**Files:**
- Modify: `frontend/src/views/DataCatalog.vue`
- Modify: `frontend/src/views/SmartQuery.vue`
- Modify: `frontend/src/components/MessageChart.vue`
- Modify: `backend/app/api/query.py`

- [x] Show metric trust status, owner, caliber version, and update status in catalog detail.
- [x] Include trusted metric context in smart-query output when the generated SQL uses a known metric formula.
- [x] Add visible trust badges to query result cards and chart cards.

### P2: Decision Loop

**Files:**
- Create: `backend/app/models/action_item.py`
- Create: `backend/app/schemas/action_item.py`
- Create: `backend/app/api/action_items.py`
- Create: `frontend/src/views/ActionItems.vue`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] Add action item model and API.
- [ ] Allow anomalies/insights/query results to create action items.
- [ ] Add owner, due date, status, linked metric/dataset/dashboard, and outcome tracking.

### P3: Scenario Workspaces

**Files:**
- Create: `backend/app/models/scenario.py`
- Create: `backend/app/api/scenarios.py`
- Create: `frontend/src/views/ScenarioWorkspace.vue`

- [ ] Add role/scenario definitions for daily operating views.
- [ ] Bind trusted metrics, dashboards, alerts, and action items to scenario workspaces.
- [ ] Make the product open into a useful daily operating context instead of a generic tool list.
