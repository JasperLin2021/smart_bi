# Smart BI

Smart BI is a Vue 3 and FastAPI business intelligence application.

## Production Deployment

Prerequisites:

- Docker Engine with Docker Compose v2
- A host port available for the frontend, default `16006`

Create the production environment file:

```bash
cp .env.example .env
```

Edit `.env` and replace every `change_me` value. At minimum set:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`, keeping it consistent with the Postgres user, password, and database
- `JWT_SECRET`
- LLM and Cube API settings if those integrations are used
- GoView settings if the 大屏中心 integration is enabled:
  `GOVIEW_BASE_URL`, `GOVIEW_EMBED_BASE_URL`, and `GOVIEW_BRIDGE_SECRET`
- Doris settings if the 数据平台 acceleration layer is enabled:
  set `DORIS_ENABLED=true` and review `DORIS_*` values.

Build and start the stack:

```bash
docker compose up -d --build
```

Open the frontend:

```text
http://localhost:16006
```

The production stack contains:

- `frontend`: Nginx serving the compiled Vue app and proxying `/api` to the backend
- `backend`: FastAPI running on the internal Docker network at port `8001`
- `postgres`: PostgreSQL 16 with persistent data in the `postgres_data` volume
- `backend_uploads`: persistent Excel upload storage

Optional OLAP acceleration:

```bash
docker compose --profile olap up -d --build
```

This starts Apache Doris FE/BE using the official runtime images
`apache/doris:fe-2.1.11` and `apache/doris:be-2.1.11`. The backend then
uses Doris for data-set materialization when `DORIS_ENABLED=true`; existing
direct database and Excel paths continue to work as fallback.

## Enterprise WeChat Integration

企业微信登录和应用消息在前端「系统管理 / 企业微信集成」中配置，不需要把应用 Secret 写入 `.env`。

配置步骤：

1. 在企业微信自建应用中准备 `CorpID`、`AgentID`、`Secret`。
2. 把回调地址设置为 `https://你的域名/api/auth/wechat-work/callback`，并在企业微信后台配置可信域名。
3. 超级管理员登录 Smart BI，进入「系统管理 / 企业微信集成」保存基础配置并启用。
4. 在「组织绑定」中把企业微信 `CorpID` 绑定到 Smart BI 的本地企业。
5. 在「部门权限」中按企业微信部门 ID 映射本地角色、数据范围、菜单权限和操作权限。

外部部门只允许映射为 `user` 或 `org_admin`；`super_admin` 仍需在 Smart BI 本地手动授予。预警、定时报告、行动项、评论、看板分享和审批提醒会通过统一消息投递服务流转到企业微信应用消息，投递结果可在同一页面查看。

## Data Access Layer

左侧「数据接入」一级菜单集中放置分析前的数据准备能力：

- 接入总览：查看数据源、数据集、刷新任务、Doris 平台和最近任务运维状态。
- 数据源管理：统一维护数据库、Excel 和后续 API / SaaS 连接器。
- 数据集开发：选择字段、筛选、聚合、语义层、刷新和发布数据集。
- 数据平台：管理 Doris 物化和增量刷新。
- 数据目录：沉淀可复用的数据资产。

Default seeded accounts are created on first backend startup:

| Role | Username | Password |
| --- | --- | --- |
| Super admin | `admin` | `admin123` |
| Carsem admin | `carsem_admin` | `carsem123` |
| Carsem metric certifier | `carsem_certifier` | `certifier123` |
| Carsem user | `carsem` | `carsem123` |
| Nexteer admin | `nexteer_admin` | `nexteer123` |
| Nexteer metric certifier | `nexteer_certifier` | `certifier123` |
| Nexteer user | `nexteer` | `nexteer123` |

Change these passwords immediately after first login in any exposed environment.

Useful commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

## Local Development

Backend:

```bash
cd backend
uv sync
DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

When deploying an existing environment, run the Alembic migration before starting
the backend image for the first time after an upgrade:

```bash
cd backend
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/smart_bi uv run alembic upgrade head
```

Frontend:

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- --host 0.0.0.0 --port 16006
```
