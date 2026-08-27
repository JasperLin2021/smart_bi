# Smart BI 项目开发约定

企业级 AI-Native BI 平台。本文件供 AI 与开发者协同编码时参考，保持精简、可执行。

> 注：本项目未集成 graphify 知识图谱（无 `graphify-out/` 目录，PyPI 上也不存在 graphify 包），此前模板规则已移除。分析代码请直接阅读源码或使用 LSP 语义工具。

## 项目结构

- `backend/` — FastAPI 后端（Python 3.12、SQLAlchemy 2、Alembic），依赖用 `uv` 管理
- `frontend/` — Vue 3 + TypeScript + Vite + Element Plus + ECharts 单页应用
- `agent/` — 对话式 AI 报表生成 Agent 服务（Node >= 22.19、tsx、fastify）
- `docs/` — 产品文档、实施计划与 README 图片资产
- 根目录 `docker-compose*.yml` — 默认/开发/生产三套部署配置

## 后端工作流（backend/）

```bash
cd backend
uv sync                          # 安装依赖（基于 pyproject.toml / uv.lock）
DATABASE_URL=sqlite:///./smartbi.db uv run alembic upgrade head   # 迁移
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload  # 启动
uv run pytest                    # 测试
uv run ruff check .              # Lint（已启用 E9/F63/F7/F82/F401/F811）
```

## 前端工作流（frontend/）

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- --host 0.0.0.0 --port 16006   # 热更新开发
npm run build                    # 生产构建
npm run typecheck                # vue-tsc 类型检查
npm run test:static              # Node 静态测试（tests/*.mjs）
npm run test:ui                  # Playwright UI 审计（需目标地址可访问）
```

## Agent 服务工作流（agent/）

```bash
cd agent
npm install
npm run dev                      # tsx watch，读取 .env
npm run build                    # tsc 编译到 dist/
npm start                        # node dist/server.js
npm test                         # smoke 测试
```

## Docker 部署

- 默认快速预览：`docker compose up -d --build`（自动导入 `mock_data.sql`），访问 `http://localhost:16006`
- 开发环境：`docker compose --env-file .env.development -f docker-compose.dev.yml up -d --build`
- 生产环境：`docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`
- 示例数据：`mock_data.sql`（Compose 演示）、`demo_data_crossborder.sql`（跨域演示数据）、`demo_setup.py` / `feature_demo_setup.py`
- 演示账号：`admin/admin123`、`nexteer_admin/nexteer123`（仅 `ENVIRONMENT=development` 自动创建）

## 编码约定

- **后端**：类型明确的 Python、FastAPI 既有模式、SQLAlchemy 2 风格、Alembic 迁移、为改动补充聚焦测试
- **前端**：Vue 3 Composition API、TypeScript、Element Plus 约定、响应式界面
- **安全**：不提交密钥、不绕过权限、破坏性迁移必须有回退说明
- **文档**：行为、部署方式或运维流程变化时，同步更新 README 或 docs/
- **提交**：使用 Conventional Commit 风格，改动聚焦、可复现

## 验证改动后需执行的检查

按修改范围运行对应检查（见上方各层工作流）：后端 `pytest` + `ruff`，前端 `typecheck` + `test:static` + `build`，涉及页面交互可补 `test:ui`。
