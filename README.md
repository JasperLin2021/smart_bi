<div align="center">

<img src="docs/assets/hero.png" alt="Smart BI enterprise analytics workspace" width="100%" />

# Smart BI

**Enterprise-grade, AI-powered business intelligence platform**<br>
**企业级 AI 驱动商业智能平台**

Smart BI brings data access, semantic datasets, trusted metrics, AI-assisted analysis,
dashboards, alerts, actions, permissions, and auditability into one open-source product.

Smart BI 将数据接入、语义数据集、可信指标、AI 问数、看板、大屏、预警、行动闭环、权限与审计整合为一个开源产品。

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)

[Overview](#overview--项目概览) ·
[Features](#features--核心能力) ·
[Architecture](#architecture--技术架构) ·
[Quick Start](#quick-start--快速开始) ·
[Development](#development--本地开发) ·
[Security](#security-and-governance--安全与治理)

</div>

---

## Overview / 项目概览

Smart BI is designed for teams that need more than a charting demo. It focuses on the
operational path from raw enterprise data to governed insight and follow-up action:

Smart BI 面向需要真实落地的企业 BI 场景，而不是简单图表 Demo。它覆盖从企业数据接入到治理分析、指标认证、业务预警和行动闭环的完整路径：

- Connect to databases and files, then model them as reusable semantic datasets.
- Ask business questions in natural language and let the AI planner produce explainable SQL and charts.
- Govern metric definitions through certification, lineage, ownership, and dataset binding.
- Publish dashboards and big-screen views for operational teams.
- Trigger alerts, scheduled reports, Enterprise WeChat notifications, and action items.
- Protect administrative and business workflows with multi-tenant RBAC, action permissions, safe-delete checks, and audit logs.

- 接入数据库和文件，并沉淀为可复用的语义数据集。
- 使用自然语言问数，由 AI Planner 生成可解释 SQL 与图表。
- 通过认证、血缘、负责人和数据集绑定治理可信指标。
- 发布业务看板和大屏，支撑运营团队实时决策。
- 触发智能预警、定时报告、企业微信消息和行动项派单。
- 通过多租户 RBAC、操作权限、安全删除检查和审计日志保护关键流程。

## Features / 核心能力

<img src="docs/assets/features.png" alt="Smart BI feature map" width="100%" />

| Area | English | 中文 |
| --- | --- | --- |
| AI analysis | Natural-language questions, SQL generation, multi-turn context, chart suggestions, and query history. | 自然语言问数、SQL 生成、多轮上下文、图表建议和查询历史。 |
| Semantic datasets | Dataset modeling, field mapping, joins, preview, publishing, refresh logs, and optional OLAP materialization. | 数据集建模、字段映射、关联关系、预览、发布、刷新日志和可选 OLAP 物化。 |
| Trusted metrics | Certification workflow, dataset-only binding, lineage, trust signals, and prompt synchronization. | 指标认证流程、仅绑定数据集、血缘、可信信号和提示词同步。 |
| Dashboards | Dashboard center, pinned charts, comments, templates, sharing, and embedded views. | 看板中心、图表固钉、评论、模板、分享和嵌入视图。 |
| Big screens | GoView integration plus an internal big-screen center for operational visualization. | 集成 GoView，同时提供内置大屏中心。 |
| Alerts and reports | Dataset-scoped alert rules, scheduler, notification delivery, and scheduled reports. | 基于数据集的预警规则、调度器、消息投递和定时报告。 |
| Data catalog | Asset registry, category tree, field-level metadata, lineage graph, subscriptions, and usage statistics. | 数据资产登记、目录树、字段级元数据、血缘图、订阅和使用统计。 |
| Data access | MySQL, PostgreSQL, Excel, SQL Server, ClickHouse-style connectors, and connector sync foundations. | MySQL、PostgreSQL、Excel、SQL Server、ClickHouse 类连接器和同步框架。 |
| Governance | Multi-tenant RBAC, menu permissions, action permissions, user overrides, RLS foundation, and audit logs. | 多租户 RBAC、菜单权限、操作权限、用户级覆盖、RLS 基础和审计日志。 |
| Safe deletion | Deletion is blocked when referenced by dependent entities, with actionable error details. | 删除被其他实体引用的资源时会阻止删除，并返回可操作的提示。 |
| Enterprise WeChat | QR-code login, organization binding, department permission mapping, and message delivery records. | 企业微信扫码登录、组织绑定、部门权限映射和消息投递记录。 |
| Operations | Access requests, action items, operations view, and closed-loop follow-up tracking. | 访问申请、行动项、运营视图和问题闭环跟踪。 |

## Architecture / 技术架构

<img src="docs/assets/architecture.png" alt="Smart BI system architecture" width="100%" />

```text
Browser / Embedded View
        |
        v
Vue 3 + TypeScript + Vite + Element Plus + ECharts + Vue Flow
        |
        v
Nginx SPA proxy -> FastAPI backend -> SQLAlchemy / Alembic
                         |
                         +-- AI planner and OpenAI-compatible LLM adapter
                         +-- Semantic layer and SQL guardrails
                         +-- Alert scheduler and message dispatcher
                         +-- Permission resolver, safe-delete guard, audit writer
                         |
                         +-- PostgreSQL 16 primary store
                         +-- Apache Doris optional OLAP materialization
                         +-- Enterprise WeChat / GoView / external connectors
```

| Layer | Stack | Notes |
| --- | --- | --- |
| Frontend | Vue 3, TypeScript, Vite, Element Plus | SPA, operational UI, dashboard builder, admin console. |
| Visualization | ECharts, Vue Flow | Charts, metric lineage, catalog lineage, DAG-style interactions. |
| Backend | Python 3.12, FastAPI 0.115, Pydantic Settings | API service, authentication, governance, AI orchestration. |
| Persistence | PostgreSQL 16, SQLAlchemy 2, Alembic | Main transactional store and reproducible migrations. |
| OLAP | Apache Doris 2.1, optional Docker Compose profile | Dataset materialization and accelerated analytical queries. |
| AI | OpenAI-compatible API | Works with OpenAI, Azure OpenAI, local gateways, and compatible models. |
| Integrations | Enterprise WeChat, GoView, connector framework | Login, messaging, big-screen launch, external data sync foundation. |

## Quick Start / 快速开始

### Prerequisites / 前置要求

- Docker Engine 24+ and Docker Compose v2.
- Git and a shell environment.
- Host port `16006` available for the frontend container.
- An OpenAI-compatible LLM endpoint if AI query generation is enabled.

- Docker Engine 24+ 与 Docker Compose v2。
- Git 与基础 Shell 环境。
- 主机端口 `16006` 可用于前端容器。
- 如需启用 AI 问数，需要 OpenAI 兼容的 LLM 服务。

### Run with Docker Compose / 使用 Docker Compose 启动

```bash
git clone https://github.com/Yuki1999/smart_bi.git
cd smart_bi

cp .env.example .env
# Edit .env before exposing the service publicly.
# 对外暴露前请先修改 .env 中的密码、JWT_SECRET 和 LLM 配置。

docker compose up -d --build

open http://localhost:16006
```

Default services:

| Service | Default | Description |
| --- | --- | --- |
| Frontend | `http://localhost:16006` | Nginx-served SPA and `/api` proxy. |
| Backend | internal `8001` | FastAPI service exposed to the frontend container. |
| PostgreSQL | internal `5432` | Primary database. |
| Doris | optional profile | Start only when OLAP acceleration is needed. |

### Default demo accounts / 默认演示账号

These accounts are initialized for local evaluation. Change every default password before
using the system in a shared or public environment.

以下账号用于本地演示。任何共享或公网环境上线前都必须修改所有默认密码。

| Role | Username | Password |
| --- | --- | --- |
| Super administrator / 超级管理员 | `admin` | `admin123` |
| Organization administrator / 企业管理员 | `nexteer_admin` | `nexteer123` |
| Department administrator / 部门管理员 | `zhang_dept` | `dept123` |
| Standard user / 普通用户 | `nexteer` | `nexteer123` |

### Optional OLAP acceleration / 可选 OLAP 加速

```bash
docker compose --profile olap up -d --build
```

Then enable Doris in `.env`:

```env
DORIS_ENABLED=true
DORIS_HOST=doris-fe
DORIS_QUERY_PORT=9030
DORIS_HTTP_PORT=8030
```

## Configuration / 配置

The repository includes `.env.example` as the starting point for deployment.

仓库提供 `.env.example` 作为部署配置模板。

```env
POSTGRES_DB=smart_bi
POSTGRES_USER=smart_bi
POSTGRES_PASSWORD=change_me_strong_database_password

DATABASE_URL=postgresql+psycopg2://smart_bi:change_me_strong_database_password@postgres:5432/smart_bi
JWT_SECRET=change_me_to_a_long_random_secret

LLM_PROVIDER=custom
LLM_API_BASE=http://host.docker.internal:8001/v1
LLM_API_KEY=change_me
LLM_MODEL=gpt-4o-mini

FRONTEND_PORT=16006
```

GoView integration:

```env
GOVIEW_ENABLED=true
GOVIEW_BASE_URL=http://host.docker.internal:3000
GOVIEW_EMBED_BASE_URL=http://host.docker.internal:3000
GOVIEW_BRIDGE_SECRET=change_me_to_a_long_random_secret
```

Enterprise WeChat is configured inside the application so secrets and department mappings
can be managed by administrators:

企业微信集成在系统内配置，便于管理员管理密钥、组织绑定和部门权限映射：

1. Open `System Management -> Enterprise WeChat Integration`.
2. Configure `CorpID`, `AgentID`, `Secret`, and callback URL.
3. Bind enterprise organizations.
4. Map departments to roles, menu permissions, action permissions, and data scope.

## Development / 本地开发

### Backend / 后端

```bash
cd backend
uv sync

DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8002 --reload
```

### Frontend / 前端

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- \
  --host 0.0.0.0 --port 16006
```

### Database migration / 数据库迁移

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_bi \
  uv run alembic upgrade head
```

## Testing / 测试

Run the checks that match the layer you changed:

按修改范围运行对应检查：

```bash
# Backend unit and API tests
cd backend
uv run pytest

# Frontend static tests
cd frontend
npm run test:static

# Frontend production build
cd frontend
npm run build

# UI audit, requires the target app URL to be reachable
cd frontend
npm run test:ui
```

Current test coverage includes permission resolution, safe deletion, metric binding,
dataset-scoped alerts and reports, semantic layer behavior, GoView integration,
Enterprise WeChat integration, UI navigation, and product completion checks.

当前测试覆盖权限解析、安全删除、指标绑定、基于数据集的预警与报告、语义层、GoView、企业微信、UI 导航和产品完整性检查。

## Security and Governance / 安全与治理

Smart BI treats governance as a product capability rather than an afterthought.

Smart BI 将治理能力作为产品内核，而不是部署后的补丁。

- Multi-tenant RBAC with platform, organization, department, and user roles.
- Separate menu permissions and action permissions for least-privilege administration.
- Per-user permission overrides for exceptional access without changing base roles.
- Data scope controls and RLS foundation for tenant-aware access.
- Safe-delete guards that block deletion when datasets, metrics, alerts, reports, dashboards, users, or other entities are still referenced.
- Audit logs for administrative and business actions.
- Enterprise WeChat mappings for external organization and department permission sync.

- 多租户 RBAC，覆盖平台、企业、部门和用户角色。
- 菜单权限与操作权限分离，支持最小权限管理。
- 用户级权限覆盖，用于处理临时或特殊授权。
- 数据范围控制和 RLS 基础能力，服务租户隔离。
- 安全删除保护：当数据集、指标、预警、报告、看板、用户等仍被引用时阻止删除。
- 管理动作和业务动作审计日志。
- 企业微信组织和部门映射，用于外部身份与权限同步。

Recommended production hardening:

生产环境建议：

- Replace all demo passwords and rotate `JWT_SECRET`.
- Run behind HTTPS and a trusted reverse proxy.
- Restrict database and Doris ports to the private network.
- Store real LLM keys and integration secrets outside source control.
- Back up PostgreSQL and uploaded assets before upgrades.
- Review audit logs and permission mappings after each role policy change.

## Project Structure / 项目结构

```text
smart_bi/
├── backend/                 # FastAPI service, SQLAlchemy models, Alembic migrations, tests
├── frontend/                # Vue 3 SPA, views, components, static tests, UI audit
├── docs/                    # Product docs, implementation plans, README assets
├── docker-compose.yml       # Production-style local deployment
├── .env.example             # Deployment configuration template
├── mock_data.sql            # Demo data for realistic evaluation
├── LICENSE                  # MIT license
└── README.md
```

## Roadmap / 路线图

Completed:

- Multi-tenant RBAC, action permissions, and user-level overrides.
- AI-assisted query workflow and dataset-scoped semantic analysis.
- Dataset semantic layer, publishing workflow, refresh logs, and preview.
- Trusted metric certification with dataset binding and lineage.
- Data catalog, asset lineage, subscriptions, and usage statistics.
- Safe-delete checks across referenced business entities.
- Dashboard center, pinned charts, comments, templates, and embedded views.
- GoView big-screen integration.
- Enterprise WeChat login, mappings, and message delivery.
- Apache Doris optional OLAP acceleration.

Planned:

- Deeper row-level and column-level security policy authoring.
- Dataset API export for REST and CSV consumers.
- More managed connectors such as Snowflake, S3, and additional SaaS systems.
- Embed SDK for third-party applications.
- Full product internationalization.
- More deployment profiles for Kubernetes and cloud-native operations.

已完成：

- 多租户 RBAC、操作权限和用户级权限覆盖。
- AI 问数流程和基于数据集的语义分析。
- 数据集语义层、发布流程、刷新日志和预览。
- 可信指标认证、数据集绑定和血缘。
- 数据目录、资产血缘、订阅和使用统计。
- 跨业务实体引用的安全删除检查。
- 看板中心、图表固钉、评论、模板和嵌入视图。
- GoView 大屏集成。
- 企业微信登录、映射和消息投递。
- Apache Doris 可选 OLAP 加速。

计划中：

- 更完整的行级和列级权限策略配置。
- 面向 REST 和 CSV 消费方的数据集 API 导出。
- 更多托管连接器，如 Snowflake、S3 和其他 SaaS 系统。
- 面向第三方系统的 Embed SDK。
- 完整产品国际化。
- Kubernetes 和云原生部署配置。

## Contributing / 参与贡献

Contributions are welcome. Please keep changes focused, reproducible, and covered by
the relevant tests.

欢迎贡献代码。请保持改动聚焦、可复现，并补充对应测试。

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Install dependencies with `uv` for backend and `npm` for frontend.
4. Run the relevant backend, frontend, or UI checks.
5. Commit using a clear Conventional Commit style message.
6. Open a Pull Request with context, screenshots for UI changes, and validation notes.

Code expectations:

- Backend: typed Python, FastAPI patterns, SQLAlchemy 2 style, Alembic migrations, focused tests.
- Frontend: Vue 3 Composition API, TypeScript, Element Plus conventions, responsive UI.
- Security: no secrets in commits, no permission bypasses, no destructive migrations without a rollback story.
- Documentation: update README or product docs when behavior, setup, or operator workflows change.

## License / 许可证

[MIT License](LICENSE)<br>
Copyright (c) 2025 Smart BI Contributors
