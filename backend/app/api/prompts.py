from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.datasource import DataSource
from app.models.user import User
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptConfig(BaseModel):
    datasource_id: int
    metadata_prompt: Optional[str] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None


class PromptResponse(BaseModel):
    datasource_id: int
    metadata_prompt: Optional[str] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None


@router.get("/config")
def get_prompt_config(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限访问")

    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    from app.core.llm import DEFAULT_TEXT2SQL_PROMPT

    return {
        "datasource_id": ds.id,
        "metadata_prompt": ds.metadata_prompt,
        "metrics_prompt": ds.metrics_prompt,
        "text2sql_prompt": ds.text2sql_prompt,
        "default_text2sql_prompt": DEFAULT_TEXT2SQL_PROMPT,
    }


@router.put("/config")
def update_prompt_config(
    payload: PromptConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限修改")

    ds = db.query(DataSource).filter(DataSource.id == payload.datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    if payload.metadata_prompt is not None:
        ds.metadata_prompt = payload.metadata_prompt
    if payload.metrics_prompt is not None:
        ds.metrics_prompt = payload.metrics_prompt
    if payload.text2sql_prompt is not None:
        ds.text2sql_prompt = payload.text2sql_prompt

    db.commit()
    db.refresh(ds)

    return {
        "datasource_id": ds.id,
        "metadata_prompt": ds.metadata_prompt,
        "metrics_prompt": ds.metrics_prompt,
        "text2sql_prompt": ds.text2sql_prompt,
    }


@router.post("/reset")
def reset_prompts(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限修改")

    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if ds:
        ds.text2sql_prompt = None
        db.commit()

    return {"status": "ok"}
