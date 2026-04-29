from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.query import router as query_router
from app.api.settings import router as settings_router
from app.api.prompts import router as prompts_router
from app.api.metrics import router as metrics_router
from app.api.pinned_charts import router as pinned_charts_router
from app.api.datasource import router as datasource_router
from app.api.organization import router as organization_router
from app.api.users import router as users_router
from app.api.agent import router as agent_router
from app.api.alerts import router as alerts_router
from app.api.scheduled_reports import router as scheduled_reports_router
from app.api.catalog import router as catalog_router
from app.api.dashboards import router as dashboards_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(query_router)
api_router.include_router(settings_router)
api_router.include_router(prompts_router)
api_router.include_router(metrics_router)
api_router.include_router(pinned_charts_router)
api_router.include_router(datasource_router)
api_router.include_router(organization_router)
api_router.include_router(users_router)
api_router.include_router(agent_router)
api_router.include_router(alerts_router)
api_router.include_router(scheduled_reports_router)
api_router.include_router(catalog_router)
api_router.include_router(dashboards_router)
