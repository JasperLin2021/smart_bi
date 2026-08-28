---
name: 编辑可信指标-实时预览展示后端SQL
overview: 在"编辑可信指标"对话框的"实时数据预览"区域，点击"刷新"后除显示预览数据外，额外展示一行（或区块）完整的后端实际 SQL 查询语句，支持一键复制。后端无需改动（接口已经返回 query.sql），仅扩展前端展示逻辑与类型。
todos:
  - id: enhance-preview-types
    content: 增强 MetricPreviewResult 类型，将 query 改为强类型 MetricPreviewQuery（含 sql 可选字段）
    status: completed
  - id: add-preview-sql-state
    content: 新增 metricPreviewSql 状态并在 resetMetricPreview/fetchMetricPreview 中读写
    status: completed
    dependencies:
      - enhance-preview-types
  - id: render-sql-block
    content: 在 metric-preview-panel 模板的 el-table 下方增加可折叠 SQL 块与复制按钮
    status: completed
    dependencies:
      - add-preview-sql-state
  - id: style-sql-block
    content: 为 SQL 块补充 scoped 样式（等宽字体、折叠区、复制按钮对齐）
    status: completed
    dependencies:
      - render-sql-block
---

## 产品概述

在"编辑可信指标"对话框的"实时数据预览"面板中，点击"刷新"按钮后，除了展示当前预览结果（行数、表格数据），再额外展示一段完整、可复制、逐字呈现的后端实际 SQL 查询语句，便于指标开发/运维人员直观核对预览背后的查询逻辑。

## 核心特性

- 刷新预览后，下方追加一段 SQL 语句展示区，呈现后端在本次预览中真实执行的 SQL（SELECT / FROM / JOIN / WHERE / GROUP BY / ORDER BY / LIMIT）。
- SQL 区支持一键复制到剪贴板，并给出成功/失败 Toast 反馈，复用项目内 `DashboardCenter.vue` 的 `navigator.clipboard.writeText + ElMessage` 模式。
- 默认以折叠/可展开区域呈现，避免占用默认预览空间；折叠标题显示"查看后端 SQL"，避免在错误态/未预览时出现空内容。
- 切换预览维度、保存指标后自动刷新，SQL 区同步更新；预览失败时 SQL 区隐藏，错误文案继续展示。
- 不改变现有预览主流程（行数、表格、刷新按钮行为），向后兼容。

## 技术栈

- 前端：Vue 3 + `<script setup>` 组合式 API + TypeScript + Element Plus（沿用项目约定）
- 网络：复用现有 `axios.post<MetricPreviewResult>(/api/metrics/${id}/preview, …)`，不新增封装层
- 样式：项目内 `<style scoped>`，沿用 `.caliber-panel` / `.metric-preview-panel` 既有样式
- 复制：原生 `navigator.clipboard.writeText` + Element Plus 全局 `ElMessage`

## 实现思路

后端已具备能力：路由 `POST /api/metrics/{metric_id}/preview`（`backend/app/api/metrics.py:1354-1410`）的响应体中已经返回了 `query.sql` 字段（由 `_metric_preview_plan` 在 `backend/app/api/metrics.py:471-518` 通过 `"\n".join(sql_parts)` 生成）。本次只动前端，从响应中读取并展示，不修改后端契约、不新增依赖、不改动 SQL 生成逻辑。

## 关键决策

- **只动前端**：后端契约已就绪，Pydantic `MetricPreviewResponse` 使用 `dict[str, Any]` 兜底，前端只读取 `query?.sql` 即可，不会破坏既有调用。
- **类型增强**：`MetricPreviewResult.query` 由 `Record<string, any>` 改为可选的强类型 `MetricPreviewQuery { sql?: string; dimensions?: string[]; metric_column?: string; limit?: number }`，便于将来取其他字段。
- **状态新增**：增加 `metricPreviewSql = ref<string>("")`，与 `metricPreviewColumns / Rows / RowCount / Error` 并列；`resetMetricPreview` 中清空；`fetchMetricPreview` 成功路径中赋值、失败路径中清空。
- **UI 位置**：放在"实时数据预览"面板内、`el-table` 下方，使用 Element Plus `<el-collapse>` 或更轻量的 `<details>/<summary>`（与面板视觉一致，无需引入图标依赖）。只在 SQL 非空、且当前无错误时渲染。
- **复制按钮**：与 `DashboardCenter.vue:830-835` 的 `copyEmbedCode` 同款写法，避免引入新依赖。
- **可访问性**：`<details>`/`<summary>` 与 `aria-label` 提供键盘可达，复制按钮有 `aria-label` 描述（项目其他交互按钮已使用该模式，例如 `aria-label="删除过滤规则"`）。

## 实施注意事项（执行细节）

- **零后端影响**：不改 `backend/app/api/metrics.py`、不改 `backend/app/schemas/metric.py`，避免触发 Alembic / OpenAPI 变更。
- **可逆性**：仅新增 ref / template 节点 / scoped 样式，回滚代价低。
- **样式克制**：SQL 块使用项目既有的 `pre`/等宽字体观感（参考 `.caliber-panel` 内的"公式预览"代码块），避免引入新 CSS 变量。
- **性能**：复制仅在用户点击时触发；模板中 SQL 长度可达 1–4KB，使用 CSS `white-space: pre-wrap; max-height` 控制最大高度，不做语法高亮（避免引入新依赖）。
- **日志/敏感信息**：SQL 由后端自己拼接，未包含用户输入参数化值；不向控制台/日志打印。

## 目录结构

仅一个文件改动：

```
e:/smart_bi/frontend/
└── src/
    └── views/
        └── MetricSettings.vue   # [MODIFY] 在"实时数据预览"面板中追加 SQL 展示区；增强 MetricPreviewResult 类型与 fetchMetricPreview
```