from fastapi import APIRouter, Depends
from fastapi_cache.decorator import cache
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
@cache(expire=60)
def summary(current_user: User = Depends(get_current_user)):
    metrics = []
    charts = []
    alerts = []
    return {"metrics": metrics, "charts": charts, "alerts": alerts}
