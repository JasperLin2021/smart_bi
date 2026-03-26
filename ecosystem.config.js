module.exports = {
  apps: [
    {
      name: "smart-bi-backend",
      cwd: "./backend",
      script: "uvicorn",
      args: "app.main:app --host 0.0.0.0 --port 8000",
      interpreter: "python3",
      env: {
        PYTHONUNBUFFERED: "1"
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "smart-bi-frontend",
      cwd: "./frontend",
      script: "npm",
      args: "run dev -- --host",
      watch: false,
      autorestart: true,
      max_restarts: 10
    }
  ]
}
