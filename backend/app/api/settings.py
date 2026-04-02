from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.llm_setting import LlmSetting
from app.models.user import User
from app.schemas.settings import LlmConfigOut, LlmConfigUpdate, LlmConfigTestRequest
from app.core.llm import (
    get_default_llm_config,
    normalize_llm_config,
    set_llm_config_cache,
    test_llm_connection,
)

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
        default_config = normalize_llm_config(get_default_llm_config())
        record = LlmSetting(
            provider=default_config["provider"],
            base_url=default_config["base_url"],
            api_key=default_config["api_key"],
            model=default_config["model"],
            temperature=default_config["temperature"],
            agent_planner_mode="llm_only",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "agent_planner_mode": record.agent_planner_mode or "llm_only",
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
            normalize_llm_config(
                {
                    "provider": record.provider,
                    "base_url": record.base_url,
                    "api_key": record.api_key,
                    "model": record.model,
                    "temperature": record.temperature,
                    "agent_planner_mode": record.agent_planner_mode or "llm_only",
                }
            )
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
            agent_planner_mode=payload.agent_planner_mode,
        )
        db.add(record)
    else:
        record.provider = payload.provider
        record.base_url = payload.base_url
        record.model = payload.model
        record.temperature = payload.temperature
        record.agent_planner_mode = payload.agent_planner_mode
        if payload.api_key is not None and payload.api_key.strip():
            record.api_key = payload.api_key.strip()
    db.commit()
    db.refresh(record)
    set_llm_config_cache(
        normalize_llm_config(
            {
                "provider": record.provider,
                "base_url": record.base_url,
                "api_key": record.api_key,
                "model": record.model,
                "temperature": record.temperature,
                "agent_planner_mode": record.agent_planner_mode or "llm_only",
            }
        )
    )
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "agent_planner_mode": record.agent_planner_mode or "llm_only",
        "api_key_set": bool(record.api_key),
    }


@router.post("/llm/test")
async def test_llm_setting(
    payload: LlmConfigTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)

    record = db.query(LlmSetting).first()
    api_key = payload.api_key.strip() if payload.api_key and payload.api_key.strip() else ""
    if not api_key and record:
        api_key = record.api_key

    if not api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    config = {
        "provider": payload.provider,
        "base_url": payload.base_url.rstrip("/"),
        "api_key": api_key,
        "model": payload.model,
        "temperature": payload.temperature,
        "agent_planner_mode": "llm_only",
    }
    return await test_llm_connection(normalize_llm_config(config))
