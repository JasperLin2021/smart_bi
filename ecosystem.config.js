module.exports = {
  apps: [
    {
      name: "smart-bi-backend-8002",
      cwd: "./backend",
      script: "/home/qqr/.local/bin/uv",
      args: "run -- uvicorn app.main:app --host 0.0.0.0 --port 8002",
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        DATABASE_URL: "postgresql+psycopg2://user:password@localhost:15432/smart_bi",
        JWT_SECRET: "dev_only_replace_if_shared",
        INTERNAL_API_SECRET: "dev_only_internal_secret",
        GOVIEW_ENABLED: "true",
        GOVIEW_BASE_URL: "http://127.0.0.1:3000",
        GOVIEW_EMBED_BASE_URL: "",
        GOVIEW_VIEW_PATH: "/#/project/items",
        GOVIEW_DESIGN_PATH: "/#/project/items"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "smart-bi-frontend-16057",
      cwd: "./frontend",
      script: "npm",
      args: "run dev -- --host 0.0.0.0 --port 16057",
      env: {
        VITE_API_PROXY_TARGET: "http://localhost:8002"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "goview-3000",
      cwd: "/home/qqr/go-view",
      script: "/home/qqr/.local/bin/pnpm",
      args: "run dev",
      interpreter: "none",
      env: {
        NODE_ENV: "development"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "smart-bi-report-agent-8010",
      cwd: "./agent",
      script: "npm",
      args: "run dev",
      env: {
        PORT: "8010",
        BACKEND_URL: "http://localhost:8002",
        JWT_SECRET: "dev_only_replace_if_shared",
        INTERNAL_API_SECRET: "dev_only_internal_secret"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    }
  ]
}
