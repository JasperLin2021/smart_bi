from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.core.olap import get_olap_status
from app.models.user import User

router = APIRouter(prefix="/olap", tags=["olap"])


def _ensure_operator(user: User) -> None:
    if user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")


@router.get("/status")
def olap_status(current_user: User = Depends(get_current_user)):
    _ensure_operator(current_user)
    return get_olap_status()


@router.post("/test-connection")
def test_olap_connection(current_user: User = Depends(get_current_user)):
    _ensure_operator(current_user)
    status = get_olap_status()
    if status["enabled"] and not status["healthy"]:
        raise HTTPException(status_code=502, detail=status["message"])
    return status
