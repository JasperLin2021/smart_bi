# Agent Skills Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为网页 Agent 增加兼容 `SKILL.md` 的 skills 生态，支持本地发现、GitHub 安装和 skill 约束规划。

**Architecture:** 后端增加 skill registry / installer / selector，并把 skill 作为 planner 的前置约束层。前端在 Agent 浮窗和数据源管理页中展示和管理 skills，但实际执行仍走现有 action catalog 和确认层。

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Pinia, Element Plus

---

### Task 1: 后端 skills registry 与安装器

**Files:**
- Create: `backend/app/core/agent_skills.py`
- Create: `backend/app/schemas/agent_skill.py`
- Modify: `backend/app/api/agent.py`
- Test: `backend/tests/test_agent_skills.py`

- [ ] Step 1: 写失败测试，覆盖本地 skill 扫描、frontmatter 读取、GitHub 路径解析。
- [ ] Step 2: 跑测试确认失败。
- [ ] Step 3: 实现 skill 扫描和 registry 输出。
- [ ] Step 4: 实现 GitHub skill 安装到 `.agent-skills`。
- [ ] Step 5: 跑测试确认通过。

### Task 2: Planner 接 skill 选择与约束

**Files:**
- Modify: `backend/app/core/agent_planner.py`
- Modify: `backend/app/core/agent_actions.py`
- Modify: `backend/app/schemas/agent.py`
- Test: `backend/tests/test_agent_skill_selection.py`

- [ ] Step 1: 写失败测试，覆盖 skill 选择和动作约束。
- [ ] Step 2: 跑测试确认失败。
- [ ] Step 3: 实现 skill selector 与 planner 注入。
- [ ] Step 4: 跑测试确认通过。

### Task 3: 前端 skills 管理与 Agent 展示

**Files:**
- Modify: `frontend/src/store/agent.ts`
- Modify: `frontend/src/components/FloatingAgent.vue`
- Modify: `frontend/src/views/DataSourceSettings.vue`
- Create: `frontend/src/components/AgentSkillsModal.vue`

- [ ] Step 1: 接 skills 列表、安装接口和当前 skill 展示。
- [ ] Step 2: 在数据源管理页增加 skills 管理入口。
- [ ] Step 3: 前端构建验证通过。

### Task 4: 集成验证

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`

- [ ] Step 1: 重启后端并验证 skills API。
- [ ] Step 2: 验证 Agent 规划响应中包含 skill。
- [ ] Step 3: 验证 GitHub 安装后可被前端看到。
