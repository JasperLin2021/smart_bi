module.exports = {
  apps: [
    {
      name: "smart-bi-backend",
      cwd: "./backend",
      script: "/home/qqr/.local/bin/uv",
      args: "run -- uvicorn app.main:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1",
        DATABASE_URL: "sqlite:////home/qqr/smart_bi/backend/smartbi.db"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "smart-bi-frontend",
      cwd: "./frontend",
      script: "npm",
      args: "run dev -- --host 0.0.0.0 --port 5173",
      watch: false,
      autorestart: true,
      max_restarts: 10
    }
  ]
}
