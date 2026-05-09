<div align="center">

# Smart BI

**Enterprise AI-powered business intelligence platform**<br>
**企业级 AI 驱动商业智能平台**

[中文](#chinese) · [English](#english)

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6.svg)](https://www.typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)

<img src="docs/assets/readme-banner.png" alt="Smart BI 中文产品 Banner，展示真实系统界面截图" width="100%" />

<sub>Banner 由当前系统截图和本地渲染文字合成，展示 Smart BI 的智能问数、可信指标和权限管理界面。</sub>

</div>

---

<a id="chinese"></a>

## 中文

### 项目概览

Smart BI 是一个企业级开源商业智能平台。它将连接器接入、语义数据集、可信指标、AI 问数、看板、大屏、预警、行动闭环、权限和审计整合为一个产品。

Smart BI 面向真实企业 BI 落地场景，而不是简单图表 Demo。它支持连接企业数据、沉淀可复用数据集、认证业务指标、用自然语言问数、发布看板、触发预警，并通过行动项完成业务闭环。

<a id="screenshots"></a>

### 界面截图总览

以下截图来自当前 Smart BI 系统界面和仓库演示数据，集中展示核心工作台、治理和运营能力。

![Smart BI 系统截图总览，集中展示 AI 问数、可信指标、看板中心、数据目录、数据源管理、预警管理和用户与权限](docs/assets/readme-screenshots.png)

<sub>图 1. 系统截图总览：AI 问数、可信指标、看板中心、数据目录、数据源管理、预警管理和用户与权限。</sub>

### 核心能力

| 模块 | 能力 |
| --- | --- |
| AI 问数 | 自然语言提问、SQL 生成、多轮上下文、图表建议和查询历史。 |
| 语义数据集 | 数据集建模、字段映射、关联关系、预览、发布、刷新日志和可选 OLAP 物化。 |
| 可信指标 | 指标认证流程、仅绑定数据集、指标血缘、可信信号和提示词同步。 |
| 看板中心 | 看板管理、图表固钉、评论、模板、分享和嵌入视图。 |
| 大屏中心 | 集成 GoView，并提供内置大屏中心用于运营可视化。 |
| 复杂报表 | 类 Excel 设计器、分页/参数/填报模板、版本管理、Excel/PDF/Word 导出任务。 |
| 自助分析 | 拖拽式工作台、维度/指标组合、同环比/累计/排名/占比、钻取和联动配置。 |
| 预警与报告 | 基于数据集的预警规则、调度器、消息投递和定时报告。 |
| 数据目录 | 资产登记、目录树、字段级元数据、血缘图、订阅和使用统计。 |
| 数据准备 | 连接器接入、数据源配置、数据集开发、Vue Flow 数据加工管道、补数、数据质量规则和可选 OLAP 物化。 |
| 治理能力 | 多租户 RBAC、菜单权限、操作权限、用户级覆盖、RLS 基础和审计日志。 |
| 安全删除 | 当资源被其他实体引用时阻止删除，并返回可操作的错误提示。 |
| 企业微信 | 扫码登录、组织绑定、部门权限映射和消息投递记录。 |
| 运营闭环 | 访问申请、行动项、运营视图和问题闭环跟踪。 |

### 技术架构

![Smart BI 中文技术架构图，展示前端体验层、后端服务层、AI 与语义层、数据与加速层、企业集成层](docs/assets/readme-architecture.png)

<sub>Vue 3 前端、FastAPI 后端、AI Planner、语义数据集、可信指标、PostgreSQL、可选 Doris、企业微信和 GoView。</sub>

```text
浏览器 / 嵌入视图
        |
        v
Vue 3 + TypeScript + Vite + Element Plus + ECharts + Vue Flow
        |
        v
Nginx SPA 代理 -> FastAPI 后端 -> SQLAlchemy / Alembic
                         |
                         +-- AI Planner 与 OpenAI 兼容 LLM 适配器
                         +-- 语义层与 SQL 安全护栏
                         +-- 复杂报表模板、导出任务与填报记录
                         +-- 数据集成 DAG、质量规则与自助分析视图
                         +-- 预警调度器与消息分发器
                         +-- 权限解析、安全删除保护、审计写入
                         |
                         +-- PostgreSQL 16 主存储
                         +-- Apache Doris 可选 OLAP 物化
                         +-- 企业微信 / GoView / 外部连接器
```

| 层级 | 技术栈 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Element Plus | 单页应用、运营界面、看板构建器和管理控制台。 |
| 可视化 | ECharts、Vue Flow | 图表、指标血缘、资产血缘和 DAG 交互。 |
| 后端 | Python 3.12、FastAPI 0.115、Pydantic Settings | API 服务、认证、治理和 AI 编排。 |
| 存储 | PostgreSQL 16、SQLAlchemy 2、Alembic | 主事务存储和可复现数据库迁移。 |
| OLAP | Apache Doris 2.1，可选 Docker Compose profile | 数据集物化和分析查询加速。 |
| AI | OpenAI 兼容 API | 支持 OpenAI、Azure OpenAI、本地网关和兼容模型。 |
| 集成 | 企业微信、GoView、连接器框架 | 登录、消息、大屏跳转和外部数据同步基础。 |

### 快速开始

前置要求：

- Docker Engine 24+ 与 Docker Compose v2。
- Git 与基础 Shell 环境。
- 主机端口 `16006` 可用于前端容器。
- 如需启用 AI 问数，需要 OpenAI 兼容的 LLM 服务。

最快本地预览仍可使用默认 Compose 文件：

```bash
git clone https://github.com/Yuki1999/smart_bi.git
cd smart_bi

cp .env.example .env
# 对外暴露前请先修改 .env 中的密码、JWT_SECRET 和 LLM 配置。

docker compose up -d --build

open http://localhost:16006
```

默认快速预览会在后端健康检查通过后自动运行一次 `demo-seed`，从 `mock_data.sql` 自动导入拟真示例数据。可用 `docker compose logs demo-seed` 查看导入结果。

默认服务：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| 前端 | `http://localhost:16006` | Nginx 托管的 SPA 和 `/api` 代理。 |
| 后端 | 容器内部 `8001` | 提供给前端容器访问的 FastAPI 服务。 |
| PostgreSQL | 容器内部 `5432` | 主数据库。 |
| 示例数据 | 一次性容器 `demo-seed` | 默认快速预览自动导入 `mock_data.sql`，退出码为 0 表示导入完成。 |
| Doris | 可选 profile | 仅在需要 OLAP 加速时启动。 |

### 部署方式

#### 开发环境部署

开发环境使用 [docker-compose.dev.yml](docker-compose.dev.yml)，面向本地调试和二次开发：前端 Vite 热更新、后端 Uvicorn reload、PostgreSQL 暴露到宿主机便于调试。

```bash
cp .env.development.example .env.development
# 按需修改 .env.development 中的 LLM、GoView 或端口配置。

docker compose --env-file .env.development -f docker-compose.dev.yml up -d --build

open http://localhost:16006
```

开发环境默认端口：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| 前端 Vite | `http://localhost:16006` | 热更新开发界面，`/api` 代理到后端容器。 |
| 后端 API | `http://localhost:8002` | FastAPI reload 模式，便于调试接口。 |
| PostgreSQL | `localhost:15432` | 仅用于本地调试的数据库端口。 |

常用开发命令：

```bash
docker compose --env-file .env.development -f docker-compose.dev.yml logs -f backend frontend
docker compose --env-file .env.development -f docker-compose.dev.yml down
```

#### 生产环境部署

生产环境使用 [docker-compose.prod.yml](docker-compose.prod.yml)，面向单机或小规模私有化部署：只暴露前端端口，PostgreSQL 和后端留在 Compose 内部网络，启动前由 `migrate` 一次性服务执行 Alembic 迁移。

```bash
cp .env.production.example .env.production
# 必须替换 .env.production 中的数据库密码、JWT_SECRET、LLM Key 和集成密钥。

docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build

docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend frontend
```

生产环境默认只暴露 `FRONTEND_PORT`，默认为 `16006`。建议在它前面放置 HTTPS 反向代理，并在代理层配置域名、证书、访问日志和请求体大小限制。

生产升级流程：

```bash
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

`postgres_prod_data` 和 `backend_prod_uploads` 是生产持久化卷。升级或迁移前请先备份 PostgreSQL 和上传文件。

默认演示账号：

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 超级管理员 | `admin` | `admin123` |
| 企业管理员 | `nexteer_admin` | `nexteer123` |
| 部门管理员 | `zhang_dept` | `dept123` |
| 普通用户 | `nexteer` | `nexteer123` |

在任何共享环境或公网环境使用前，请修改所有默认密码。

生产环境可选 OLAP 加速：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml --profile olap up -d --build
```

然后在 `.env.production` 中启用 Doris：

```env
DORIS_ENABLED=true
DORIS_HOST=doris-fe
DORIS_QUERY_PORT=9030
DORIS_HTTP_PORT=8030
```

### 示例数据

远端仓库已经包含 `mock_data.sql`、`demo_setup.py` 和 `feature_demo_setup.py`。
其中 `mock_data.sql` 是推荐的 Docker Compose 开箱即用示例数据，因为它可以在后端完成建表后直接导入 PostgreSQL。

默认快速预览命令 `docker compose up -d --build` 会自动导入 `mock_data.sql`，因此从 GitHub 克隆后启动即可看到拟真企业、数据源、数据集、指标、看板、复杂报表、数据加工管道、自助分析视图、数据目录、预警和待办数据。

示例数据包含三组 P1 企业级能力样例：

- `复杂报表`：Nexteer OEE 分页周报、RTY 质量填报月报、蓝途销售经营 Word 报告，含模板版本、导出运行和填报记录。
- `数据加工管道`：生产明细日同步、销售增量同步，含 DAG 节点、补数运行、质量规则和最近执行日志。
- `自助分析`：产线 OEE 趋势、RTY 失效模式 Pareto、客户销售贡献分析，含计算字段和钻取/联动配置。

开发环境导入完整演示数据：

```bash
docker compose --env-file .env.development -f docker-compose.dev.yml --profile demo up -d --build
docker compose --env-file .env.development -f docker-compose.dev.yml logs demo-seed
```

生产演示环境也可以使用 `docker compose --env-file .env.production -f docker-compose.prod.yml --profile demo up -d --build` 导入示例数据，但真实生产库不建议导入演示数据。`demo-seed` 是一次性容器。它会等待 PostgreSQL 和后端健康检查通过，再导入 `mock_data.sql`，输出 `Smart BI demo data imported.` 后退出。多数插入语句使用 `ON CONFLICT` 做幂等处理，因此可安全重复执行它管理的演示数据。

### 配置

仓库提供三类配置模板：`.env.example` 用于默认快速预览，`.env.development.example` 用于开发 Compose，`.env.production.example` 用于生产 Compose。

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

GoView 集成：

```env
GOVIEW_ENABLED=true
GOVIEW_BASE_URL=http://host.docker.internal:3000
GOVIEW_EMBED_BASE_URL=http://host.docker.internal:3000
GOVIEW_BRIDGE_SECRET=change_me_to_a_long_random_secret
```

企业微信集成在系统内配置，便于管理员管理密钥、组织绑定和部门权限映射：

1. 打开 `系统管理 -> 企业微信集成`。
2. 配置 `CorpID`、`AgentID`、`Secret` 和回调地址。
3. 绑定企业组织。
4. 将部门映射到角色、菜单权限、操作权限和数据范围。

### 本地开发

后端：

```bash
cd backend
uv sync

DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8002 --reload
```

前端：

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- \
  --host 0.0.0.0 --port 16006
```

数据库迁移：

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_bi \
  uv run alembic upgrade head
```

### 测试

按修改范围运行对应检查：

```bash
cd backend
uv run pytest

cd frontend
npm run test:static
npm run build

# 需要目标应用地址可访问。
npm run test:ui
```

当前测试覆盖权限解析、安全删除、指标绑定、基于数据集的预警与报告、语义层、GoView、企业微信、UI 导航和产品完整性检查。

### 安全与治理

Smart BI 将治理能力作为产品内核，而不是部署后的补丁。

- 多租户 RBAC，覆盖平台、企业、部门和用户角色。
- 菜单权限与操作权限分离，支持最小权限管理。
- 用户级权限覆盖，用于处理临时或特殊授权。
- 数据范围控制和 RLS 基础能力，服务租户隔离。
- 安全删除保护：当数据集、指标、预警、报告、看板、用户等仍被引用时阻止删除。
- 管理动作和业务动作审计日志。
- 企业微信组织和部门映射，用于外部身份与权限同步。

生产环境建议：

- 替换所有演示账号密码，并轮换 `JWT_SECRET`。
- 使用 HTTPS 和可信反向代理。
- 将数据库和 Doris 端口限制在私有网络内。
- 将真实 LLM Key 和集成密钥保存在源码仓库之外。
- 升级前备份 PostgreSQL 和上传资产。
- 每次调整角色策略后复核审计日志和权限映射。

### 项目结构

```text
smart_bi/
├── backend/                 # FastAPI 服务、SQLAlchemy 模型、Alembic 迁移、测试
├── frontend/                # Vue 3 单页应用、视图、组件、静态测试、UI 审计
├── docs/                    # 产品文档、实施计划、README 图片资产
├── docker-compose.yml       # 默认快速预览部署配置
├── docker-compose.dev.yml   # 开发环境：热更新、调试端口和本地数据库端口
├── docker-compose.prod.yml  # 生产环境：迁移任务、内部网络和持久化卷
├── .env.example             # 默认快速预览配置模板
├── .env.development.example # 开发环境配置模板
├── .env.production.example  # 生产环境配置模板
├── mock_data.sql            # 拟真演示数据
├── LICENSE                  # MIT 许可证
└── README.md
```

### 路线图

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

### 参与贡献

欢迎贡献代码。请保持改动聚焦、可复现，并补充对应测试。

1. Fork 本仓库。
2. 创建特性分支：`git checkout -b feature/your-feature`。
3. 后端使用 `uv` 安装依赖，前端使用 `npm` 安装依赖。
4. 运行与改动范围匹配的后端、前端或 UI 检查。
5. 使用清晰的 Conventional Commit 风格提交信息。
6. 创建 Pull Request，并补充背景、UI 截图和验证说明。

代码要求：

- 后端：类型明确的 Python、FastAPI 既有模式、SQLAlchemy 2 风格、Alembic 迁移和聚焦测试。
- 前端：Vue 3 Composition API、TypeScript、Element Plus 约定和响应式界面。
- 安全：不提交密钥、不绕过权限、破坏性迁移必须有回退说明。
- 文档：当行为、部署方式或运维流程变化时，同步更新 README 或产品文档。

### 许可证

[MIT License](LICENSE)<br>
Copyright (c) 2025 Smart BI Contributors

---

<a id="english"></a>

## English

### Overview

Smart BI is an enterprise-grade, open-source business intelligence platform. It brings
connector access, semantic datasets, trusted metrics, AI-assisted analysis, dashboards,
big-screen operations, alerts, actions, permissions, and auditability into one product.

It is built for teams that need a real operational BI workflow instead of a charting
demo: connect enterprise data, model it as reusable datasets, certify business metrics,
ask questions in natural language, publish dashboards, trigger alerts, and close the
loop with follow-up actions.

### Screenshots

See the [central screenshot overview](#screenshots) above. It is captured from the current Smart BI interface running with the repository's demo data, so the README reflects the real product surface instead of generated placeholder illustrations.

### Feature Map

| Area | Capability |
| --- | --- |
| AI analysis | Natural-language questions, SQL generation, multi-turn context, chart suggestions, and query history. |
| Semantic datasets | Dataset modeling, field mapping, joins, preview, publishing, refresh logs, and optional OLAP materialization. |
| Trusted metrics | Certification workflow, dataset-only binding, lineage, trust signals, and prompt synchronization. |
| Dashboards | Dashboard center, pinned charts, comments, templates, sharing, and embedded views. |
| Big screens | GoView integration plus an internal big-screen center for operational visualization. |
| Complex reports | Excel-like report designer, paginated/parameter/fill-form templates, versioning, and Excel/PDF/Word export jobs. |
| Self-service analytics | Drag-style workbench, dimension/measure composition, YoY/MoM, cumulative, rank, ratio, drill-down, and linkage settings. |
| Alerts and reports | Dataset-scoped alert rules, scheduler, notification delivery, and scheduled reports. |
| Data catalog | Asset registry, category tree, field-level metadata, lineage graph, subscriptions, and usage statistics. |
| Data preparation | Connector access, data source setup, dataset development, Vue Flow data processing pipelines, backfill runs, data quality rules, and optional OLAP materialization. |
| Governance | Multi-tenant RBAC, menu permissions, action permissions, user overrides, RLS foundation, and audit logs. |
| Safe deletion | Deletion is blocked when referenced by dependent entities, with actionable error details. |
| Enterprise WeChat | QR-code login, organization binding, department permission mapping, and message delivery records. |
| Operations | Access requests, action items, operations view, and closed-loop follow-up tracking. |

### Architecture

![Smart BI architecture diagram with Chinese labels for frontend, backend, AI semantic layer, data acceleration, and enterprise integrations](docs/assets/readme-architecture.png)

<sub>The architecture image uses Chinese labels to match the terminology used in the current product UI and documentation.</sub>

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
                         +-- Complex report templates, export jobs, fill records
                         +-- Data integration DAGs, quality rules, analysis views
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

### Quick Start

Prerequisites:

- Docker Engine 24+ and Docker Compose v2.
- Git and a shell environment.
- Host port `16006` available for the frontend container.
- An OpenAI-compatible LLM endpoint if AI query generation is enabled.

For the fastest local preview, use the default Compose file:

```bash
git clone https://github.com/Yuki1999/smart_bi.git
cd smart_bi

cp .env.example .env
# Edit .env before exposing the service publicly.

docker compose up -d --build

open http://localhost:16006
```

The default quick preview automatically imports `mock_data.sql` through the one-shot
`demo-seed` container after the backend health check passes. Check the result with
`docker compose logs demo-seed`.

Default services:

| Service | Default | Description |
| --- | --- | --- |
| Frontend | `http://localhost:16006` | Nginx-served SPA and `/api` proxy. |
| Backend | internal `8001` | FastAPI service exposed to the frontend container. |
| PostgreSQL | internal `5432` | Primary database. |
| Demo data | one-shot `demo-seed` container | Automatically imports `mock_data.sql` for the default quick preview; exit code 0 means the import completed. |
| Doris | optional profile | Start only when OLAP acceleration is needed. |

### Deployment

#### Development Deployment

The development stack uses [docker-compose.dev.yml](docker-compose.dev.yml). It is intended for local debugging and product development: Vite hot reload for the frontend, Uvicorn reload for the backend, and a host-exposed PostgreSQL port for local tools.

```bash
cp .env.development.example .env.development
# Edit .env.development if you need custom LLM, GoView, or port settings.

docker compose --env-file .env.development -f docker-compose.dev.yml up -d --build

open http://localhost:16006
```

Default development ports:

| Service | Default | Description |
| --- | --- | --- |
| Frontend Vite | `http://localhost:16006` | Hot-reload UI with `/api` proxied to the backend container. |
| Backend API | `http://localhost:8002` | FastAPI in reload mode for API debugging. |
| PostgreSQL | `localhost:15432` | Local-only database port for development tools. |

Useful development commands:

```bash
docker compose --env-file .env.development -f docker-compose.dev.yml logs -f backend frontend
docker compose --env-file .env.development -f docker-compose.dev.yml down
```

#### Production Deployment

The production stack uses [docker-compose.prod.yml](docker-compose.prod.yml). It is intended for single-node or small private deployments: only the frontend port is published, PostgreSQL and backend stay inside the Compose network, and a one-shot `migrate` service runs Alembic migrations before the backend starts.

```bash
cp .env.production.example .env.production
# Replace database password, JWT_SECRET, LLM key, and integration secrets in .env.production.

docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build

docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend frontend
```

Production publishes only `FRONTEND_PORT`, defaulting to `16006`. Put an HTTPS reverse proxy in front of it for domain routing, TLS certificates, access logs, and request-size limits.

Production upgrade flow:

```bash
git pull --ff-only
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

`postgres_prod_data` and `backend_prod_uploads` are production persistence volumes. Back up PostgreSQL and uploaded files before upgrades or migrations.

Default demo accounts:

| Role | Username | Password |
| --- | --- | --- |
| Super administrator | `admin` | `admin123` |
| Organization administrator | `nexteer_admin` | `nexteer123` |
| Department administrator | `zhang_dept` | `dept123` |
| Standard user | `nexteer` | `nexteer123` |

Change every default password before using the system in a shared or public environment.

Optional production OLAP acceleration:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml --profile olap up -d --build
```

Then enable Doris in `.env.production`:

```env
DORIS_ENABLED=true
DORIS_HOST=doris-fe
DORIS_QUERY_PORT=9030
DORIS_HTTP_PORT=8030
```

### Demo Data

The remote repository already includes `mock_data.sql`, `demo_setup.py`, and
`feature_demo_setup.py`. `mock_data.sql` is the recommended out-of-the-box dataset for
Docker Compose because it can be imported directly into PostgreSQL after the backend
has created the application tables.

The default quick-start command, `docker compose up -d --build`, automatically imports
`mock_data.sql`, so a fresh GitHub clone starts with realistic organizations, data
sources, datasets, metrics, dashboards, complex report templates, data pipelines,
self-service analysis views, catalog assets, alerts, and action items.

The demo seed now includes three P1 enterprise-capability samples:

- `Complex reports`: Nexteer OEE paginated weekly report, RTY quality fill-form report, and Lantu sales Word report, including template versions, export runs, and fill records.
- `Data pipelines`: production daily sync and sales incremental sync, including DAG nodes, backfill runs, quality rules, and recent execution logs.
- `Self-service analysis`: OEE trend analysis, RTY Pareto analysis, and customer sales contribution analysis, including calculation fields and drill/linkage settings.

To start the development stack and import the full demo dataset in one flow:

```bash
docker compose --env-file .env.development -f docker-compose.dev.yml --profile demo up -d --build
docker compose --env-file .env.development -f docker-compose.dev.yml logs demo-seed
```

Demo production deployments can also use `docker compose --env-file .env.production -f docker-compose.prod.yml --profile demo up -d --build`, but real production databases should not import demo data. The `demo-seed` service is a one-shot container. It waits for PostgreSQL and the backend health check, imports `mock_data.sql`, prints `Smart BI demo data imported.`, and exits. Most inserts are idempotent through `ON CONFLICT`, so rerunning it is safe for the demo records it manages.

### Configuration

The repository includes three configuration templates: `.env.example` for the default quick preview, `.env.development.example` for the development Compose stack, and `.env.production.example` for the production Compose stack.

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

1. Open `System Management -> Enterprise WeChat Integration`.
2. Configure `CorpID`, `AgentID`, `Secret`, and callback URL.
3. Bind enterprise organizations.
4. Map departments to roles, menu permissions, action permissions, and data scope.

### Development

Backend:

```bash
cd backend
uv sync

DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app \
  --host 0.0.0.0 --port 8002 --reload
```

Frontend:

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- \
  --host 0.0.0.0 --port 16006
```

Database migration:

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_bi \
  uv run alembic upgrade head
```

### Testing

Run the checks that match the layer you changed:

```bash
cd backend
uv run pytest

cd frontend
npm run test:static
npm run build

# Requires the target app URL to be reachable.
npm run test:ui
```

Current test coverage includes permission resolution, safe deletion, metric binding,
dataset-scoped alerts and reports, semantic layer behavior, GoView integration,
Enterprise WeChat integration, UI navigation, and product completion checks.

### Security and Governance

Smart BI treats governance as a product capability rather than an afterthought.

- Multi-tenant RBAC with platform, organization, department, and user roles.
- Separate menu permissions and action permissions for least-privilege administration.
- Per-user permission overrides for exceptional access without changing base roles.
- Data scope controls and RLS foundation for tenant-aware access.
- Safe-delete guards that block deletion when datasets, metrics, alerts, reports, dashboards, users, or other entities are still referenced.
- Audit logs for administrative and business actions.
- Enterprise WeChat mappings for external organization and department permission sync.

Recommended production hardening:

- Replace all demo passwords and rotate `JWT_SECRET`.
- Run behind HTTPS and a trusted reverse proxy.
- Restrict database and Doris ports to the private network.
- Store real LLM keys and integration secrets outside source control.
- Back up PostgreSQL and uploaded assets before upgrades.
- Review audit logs and permission mappings after each role policy change.

### Project Structure

```text
smart_bi/
├── backend/                 # FastAPI service, SQLAlchemy models, Alembic migrations, tests
├── frontend/                # Vue 3 SPA, views, components, static tests, UI audit
├── docs/                    # Product docs, implementation plans, README assets
├── docker-compose.yml       # Default quick-preview deployment
├── docker-compose.dev.yml   # Development stack: hot reload, debug ports, local database port
├── docker-compose.prod.yml  # Production stack: migration job, internal network, persistent volumes
├── .env.example             # Default quick-preview configuration template
├── .env.development.example # Development configuration template
├── .env.production.example  # Production configuration template
├── mock_data.sql            # Demo data for realistic evaluation
├── LICENSE                  # MIT license
└── README.md
```

### Roadmap

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

### Contributing

Contributions are welcome. Please keep changes focused, reproducible, and covered by
the relevant tests.

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

### License

[MIT License](LICENSE)<br>
Copyright (c) 2025 Smart BI Contributors
