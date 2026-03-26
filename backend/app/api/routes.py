from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.query import router as query_router
from app.api.settings import router as settings_router
from app.api.prompts import router as prompts_router
from app.api.metrics import router as metrics_router
from app.api.pinned_charts import router as pinned_charts_router
from app.api.datasource import router as datasource_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(query_router)
api_router.include_router(settings_router)
api_router.include_router(prompts_router)
api_router.include_router(metrics_router)
api_router.include_router(pinned_charts_router)
api_router.include_router(datasource_router)
