# Query Planner Phase1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight query planner that classifies BI questions before SQL generation and routes them through type-specific SQL guidance for better accuracy.

**Architecture:** Introduce a backend planner that emits a small structured plan using rule-first classification with LLM fallback. Feed that plan into SQL generation so detail, aggregate, distribution, and ranking questions use different prompting constraints while keeping the current SQL guard and summary guard intact.

**Tech Stack:** FastAPI, SQLAlchemy, Python unittest, existing LLM wrapper, existing SQL guard pipeline

---

### Task 1: Add planner contract and rule-first planner

**Files:**
- Create: `backend/app/core/query_planner.py`
- Test: `backend/tests/test_query_planner.py`

- [ ] **Step 1: Write failing planner tests for detail/distribution/ranking/aggregate classification**
- [ ] **Step 2: Run planner tests to verify failure**
- [ ] **Step 3: Implement minimal planner data shape and rule-first classifier**
- [ ] **Step 4: Add LLM fallback path returning normalized JSON plan**
- [ ] **Step 5: Re-run planner tests to verify pass**

### Task 2: Route SQL generation through planner-specific guidance

**Files:**
- Modify: `backend/app/core/llm.py`
- Test: `backend/tests/test_llm_query_plan_prompt.py`

- [ ] **Step 1: Write failing tests asserting plan-specific prompt guidance is injected**
- [ ] **Step 2: Run prompt tests to verify failure**
- [ ] **Step 3: Add plan-aware SQL prompt suffixes for detail, aggregate, distribution, ranking**
- [ ] **Step 4: Thread `query_plan` into SQL generation**
- [ ] **Step 5: Re-run prompt tests to verify pass**

### Task 3: Integrate planner into query execution path

**Files:**
- Modify: `backend/app/api/query.py`
- Test: `backend/tests/test_query_planner_integration.py`

- [ ] **Step 1: Write failing integration test showing ask-path obtains plan before SQL generation**
- [ ] **Step 2: Run integration test to verify failure**
- [ ] **Step 3: Plan before SQL generation and pass plan into normal + retry SQL generation path**
- [ ] **Step 4: Normalize planner context handling without breaking SQL guard and summary guard**
- [ ] **Step 5: Re-run integration test to verify pass**

### Task 4: Full verification

**Files:**
- Verify only

- [ ] **Step 1: Run targeted new tests**
- [ ] **Step 2: Run full backend test suite**
- [ ] **Step 3: Restart backend process**
- [ ] **Step 4: Verify health endpoint**
