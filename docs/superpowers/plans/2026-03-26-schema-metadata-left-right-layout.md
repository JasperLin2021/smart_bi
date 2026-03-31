# Schema Metadata Left Right Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将表结构管理弹窗改为左侧表导航、右侧页签编辑的左右布局。

**Architecture:** 保持现有 schema 数据结构和保存流程不变，只在前端弹窗组件内重组布局。新增当前选中表与当前页签状态，让表编辑集中在右侧工作区，关联关系通过页签访问。

**Tech Stack:** Vue 3, TypeScript, Element Plus, Vite

---

### Task 1: 重构表结构管理弹窗布局

**Files:**
- Modify: `frontend/src/components/SchemaMetadataModal.vue`

- [ ] Step 1: 添加当前选中表和页签状态。
- [ ] Step 2: 将模板改为左侧表导航、右侧编辑区。
- [ ] Step 3: 将字段编辑移动到右侧“字段管理”页签。
- [ ] Step 4: 将关联关系编辑移动到右侧“关联关系”页签。
- [ ] Step 5: 调整样式以适配更宽弹窗和左右布局。

### Task 2: 验证变更

**Files:**
- Modify: `frontend/src/components/SchemaMetadataModal.vue`

- [ ] Step 1: 运行前端构建验证类型与模板通过。
- [ ] Step 2: 如有构建错误，做最小修复并重新构建。
