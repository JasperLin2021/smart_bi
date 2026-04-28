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

Default seeded accounts are created on first backend startup:

| Role | Username | Password |
| --- | --- | --- |
| Super admin | `admin` | `admin123` |
| Carsem admin | `carsem_admin` | `carsem123` |
| Carsem user | `carsem` | `carsem123` |
| Nexteer admin | `nexteer_admin` | `nexteer123` |
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
DATABASE_URL=sqlite:///./smartbi.db uv run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Frontend:

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8002 npm run dev -- --host 0.0.0.0 --port 16006
```
