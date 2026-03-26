from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.llm_setting import LlmSetting
from app.models.user import User
from app.schemas.settings import LlmConfigOut, LlmConfigUpdate
from app.core.llm import get_default_llm_config, set_llm_config_cache

router = APIRouter(prefix="/settings", tags=["settings"])


def ensure_admin(user: User):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限")


@router.get("/llm", response_model=LlmConfigOut)
def get_llm_setting(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if not record:
        default_config = get_default_llm_config()
        record = LlmSetting(
            provider=default_config["provider"],
            base_url=default_config["base_url"],
            api_key=default_config["api_key"],
            model=default_config["model"],
            temperature=default_config["temperature"],
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "api_key_set": bool(record.api_key),
    }


@router.post("/llm/refresh")
def refresh_llm_cache(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if record:
        set_llm_config_cache(
            {
                "provider": record.provider,
                "base_url": record.base_url,
                "api_key": record.api_key,
                "model": record.model,
                "temperature": record.temperature,
            }
        )
    return {"status": "ok"}


@router.put("/llm", response_model=LlmConfigOut)
def update_llm_setting(
    payload: LlmConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if not record:
        record = LlmSetting(
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key or "",
            model=payload.model,
            temperature=payload.temperature,
        )
        db.add(record)
    else:
        record.provider = payload.provider
        record.base_url = payload.base_url
        record.model = payload.model
        record.temperature = payload.temperature
        if payload.api_key is not None and payload.api_key.strip():
            record.api_key = payload.api_key.strip()
    db.commit()
    db.refresh(record)
    set_llm_config_cache(
        {
            "provider": record.provider,
            "base_url": record.base_url,
            "api_key": record.api_key,
            "model": record.model,
            "temperature": record.temperature,
        }
    )
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "api_key_set": bool(record.api_key),
    }
