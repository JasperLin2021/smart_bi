# BI Gap Closure Without Semantic Layer

## Scope

Close the practical BI gaps against mature local BI products while explicitly deferring the semantic/theme model layer.

## Phase 1: Dataset Preparation Pipeline

- Persist executable dataset preparation configuration beyond UI-only field JSON.
- Support previewing a dataset from its source table with selected fields, filters, derived columns, joins, aggregations, and row limits.
- Add refresh logs so operators can see whether a dataset can be materialized successfully.
- Keep execution guarded: validate table and field identifiers with SQLAlchemy inspection, clamp preview limits, and scope datasource access by organization.

## Phase 2: Self-Service Analysis

- Add an analysis workspace backed by published datasets.
- Let users drag dimensions and measures into chart/query shelves.
- Support table, bar, line, pie, KPI, and pivot-style outputs.
- Save analysis outputs as dashboard cards.

## Phase 3: Governance And Permissions

- Add dataset-level access management for owners, org-wide visibility, and explicit shared users.
- Add reusable permission checks for dataset read, manage, publish, refresh, and export actions.
- Add audit logs for preview, refresh, publish, permission, and export actions.

## Phase 4: Refresh, Cache, And Delivery

- Add scheduled dataset refresh definitions and refresh history.
- Add cached preview/materialization metadata with row counts and timestamps.
- Add export and subscription entry points for datasets, dashboards, and analysis outputs.

## Current Slice

Implement Phase 1 backend foundation:

1. Dataset pipeline execution helpers.
2. Dataset preview API.
3. Dataset refresh API and refresh log model.
4. Alembic migration and startup compatibility columns.
5. Backend tests proving org scoping, preview output, and refresh log persistence.
