<div align="center">

<img src="docs/assets/hero.png" alt="Smart BI — Enterprise AI-Powered Business Intelligence" width="100%" />

# Smart BI

**企业级 AI 驱动商业智能平台**

一站式覆盖数据接入、语义建模、可视化分析、智能预警与行动闭环，开箱即用。

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)

[快速开始](#-快速开始) · [功能特性](#-功能特性) · [技术架构](#-技术架构) · [配置说明](#-配置说明) · [参与贡献](#-参与贡献)

</div>

---

## ✨ 功能特性

<img src="docs/assets/features.png" alt="Smart BI Feature Overview" width="100%" />

| 模块 | 能力描述 |
|------|----------|
| 🤖 **智能问数** | 自然语言转 SQL，多轮对话，AI Agent 自动规划查询步骤，结果以图表直接呈现 |
| 📊 **看板中心** | 拖拽式多维看板，支持图表固钉、跨看板复用、评论协作与嵌入分享 |
| 🖥️ **大屏中心** | 集成 GoView 大屏设计器，支持全屏展示与自动轮播 |
| 📈 **可信指标** | 指标认证体系（草稿→待认证→已认证），血缘追踪至数据集语义层 |
| 🔔 **智能预警** | 规则引擎 + 定时调度，支持站内通知与企业微信推送 |
| 📋 **行动闭环** | 问题发现→行动派单→跟进→关闭全链路，支持部门级指派 |
| 🗂️ **数据目录** | 统一资产登记，字段级目录，数据血缘 DAG，浏览热度统计，订阅通知 |
| 🗄️ **数据接入** | MySQL / PostgreSQL / Excel 多源接入，数据集语义建模，Apache Doris OLAP 加速 |
| 🔐 **企业级权限** | 多租户 RBAC（普通用户 / 部门管理员 / 企业管理员 / 超管），菜单+操作双维度权限，支持用户级个性化覆盖 |
| 🔗 **企业微信集成** | 扫码登录，部门权限映射，消息推送（预警 / 报告 / 行动项 / 审批提醒） |
| 📅 **定时报告** | 配置报告模板，定时触发，自动投递至邮件 / 企业微信 |
| 📝 **审计日志** | 全操作链路审计，管理员可按用户/时间/动作过滤查询 |

---

## 🏗️ 技术架构

<img src="docs/assets/architecture.png" alt="Smart BI Technical Architecture" width="100%" />

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Element Plus + ECharts + Vue Flow)       │
│  Nginx · SPA · /api proxy                                   │
├─────────────────────────────────────────────────────────────┤
│  Backend API (FastAPI + Python 3.11)                        │
│  JWT Auth · AI Agent Planner · Alert Scheduler              │
│  Alembic Migrations · Pydantic v2                           │
├──────────────────────────┬──────────────────────────────────┤
│  PostgreSQL 16           │  Apache Doris (Optional OLAP)    │
│  Primary store           │  Materialized acceleration       │
├──────────────────────────┴──────────────────────────────────┤
│  Integrations                                               │
│  LLM (OpenAI / Compatible) · Enterprise WeChat · GoView    │
└─────────────────────────────────────────────────────────────┘
```

**技术栈一览**

| 层级 | 技术选型 |
|------|----------|
| 前端框架 | Vue 3 · TypeScript · Vite |
| UI 组件库 | Element Plus |
| 图表引擎 | ECharts 5 · Vue Flow (DAG) |
| 后端框架 | FastAPI · Python 3.11 |
| ORM / 迁移 | SQLAlchemy 2 · Alembic |
| 数据库 | PostgreSQL 16 |
| OLAP 加速 | Apache Doris 2.1（可选） |
| 容器化 | Docker Compose |
| AI 集成 | OpenAI 兼容 API（支持本地模型） |

---

## 🚀 快速开始

### 前置要求

- Docker Engine ≥ 24 与 Docker Compose v2
- 开放主机端口（默认 `16006`）

### 一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/Yuki1999/smart_bi.git
cd smart_bi

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少设置以下必填项：
#   POSTGRES_PASSWORD   数据库密码
#   DATABASE_URL        保持与上面密码一致
#   JWT_SECRET          随机长字符串
#   LLM_API_KEY         LLM API Key（支持 OpenAI 兼容接口）

# 3. 构建并启动
docker compose up -d --build

# 4. 访问
open http://localhost:16006
```

**默认账号**（首次启动自动初始化，上线前请修改密码）

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 超级管理员 | `admin` | `admin123` |
| 企业管理员（Nexteer） | `nexteer_admin` | `nexteer123` |
| 部门管理员 | `zhang_dept` | `dept123` |
| 普通用户 | `nexteer` | `nexteer123` |

> ⚠️ **安全提示**：在任何对外暴露的环境中，请在首次登录后立即修改所有默认密码。

### 启用 OLAP 加速（可选）

```bash
# 启动 Apache Doris FE/BE
docker compose --profile olap up -d --build

# 在 .env 中启用
DORIS_ENABLED=true
```

Doris 启用后，数据集物化查询性能可提升 10–100×，现有直连和 Excel 路径继续作为 fallback。

---

## ⚙️ 配置说明

### 必填配置

```env
POSTGRES_PASSWORD=<强密码>
DATABASE_URL=postgresql+psycopg2://smart_bi:<密码>@postgres:5432/smart_bi
JWT_SECRET=<随机长字符串，建议 64 位>

# LLM（支持 OpenAI、Azure OpenAI、本地 Ollama 等兼容接口）
LLM_PROVIDER=custom
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

### GoView 大屏集成

```env
GOVIEW_ENABLED=true
GOVIEW_BASE_URL=http://your-goview-host:3000
GOVIEW_EMBED_BASE_URL=http://your-goview-host:3000
GOVIEW_BRIDGE_SECRET=<与 GoView 约定的共享密钥>
```

### 企业微信集成

无需写入 `.env`，在 Smart BI 界面中配置：

1. 进入「系统管理 → 企业微信集成」
2. 填入 `CorpID`、`AgentID`、`Secret`
3. 配置回调地址：`https://your-domain/api/auth/wechat-work/callback`
4. 在「组织绑定」中绑定企业，在「部门权限」中映射角色与权限

---

## 💻 本地开发

### 后端

```bash
cd backend
uv sync
# SQLite 快速启动
DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8002 --reload
```

### 前端

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- \
  --host 0.0.0.0 --port 16006
```

### 数据库迁移（生产升级）

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_bi \
  uv run alembic upgrade head
```

### 常用命令

```bash
docker compose ps                  # 查看容器状态
docker compose logs -f backend     # 后端实时日志
docker compose logs -f frontend    # 前端/Nginx 日志
docker compose down                # 停止并移除容器
docker compose down -v             # 同时删除数据卷（谨慎）
```

---

## 🛣️ 路线图

- [x] 多租户 RBAC 权限体系（菜单 + 操作 + 用户级覆盖）
- [x] AI 智能问数（多轮对话，Agent 规划）
- [x] 数据集语义层（字段映射、JOIN、发布）
- [x] 可信指标认证体系与数据血缘
- [x] 数据目录（资产登记、字段级、血缘 DAG、订阅通知）
- [x] 企业微信扫码登录与消息推送
- [x] GoView 大屏集成
- [x] Apache Doris OLAP 加速层
- [ ] 移动端 H5 自适应
- [ ] 行列级数据权限（RLS）
- [ ] 数据集 API 导出（REST / CSV）
- [ ] 更多数据源连接器（Snowflake、ClickHouse、S3）
- [ ] Embed SDK（无感嵌入第三方系统）
- [ ] 多语言国际化（i18n）

---

## 🤝 参与贡献

欢迎 Issue、PR 和 Discussion！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m 'feat: your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

**代码规范**

- 后端：`ruff` 格式化，类型注解，Pydantic v2 Schema
- 前端：ESLint + `vue/recommended`，TypeScript strict mode
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org)

---

## 📄 License

[MIT License](LICENSE) · Copyright © 2025 Smart BI Contributors
