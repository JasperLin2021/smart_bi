from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.rls_rule import RLSRule
from app.models.datasource import DataSource
from app.models.user import User

router = APIRouter(prefix="/datasources", tags=["rls"])

ALLOWED_OPERATORS = {"=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "LIKE"}


class RLSRuleCreate(BaseModel):
    table_name: str
    column_name: str
    operator: str = "="
    filter_value: str
    org_id: Optional[int] = None
    user_id: Optional[int] = None
    is_active: int = 1


class RLSRuleUpdate(BaseModel):
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    operator: Optional[str] = None
    filter_value: Optional[str] = None
    org_id: Optional[int] = None
    user_id: Optional[int] = None
    is_active: Optional[int] = None


class RLSRuleOut(BaseModel):
    id: int
    datasource_id: int
    org_id: Optional[int]
    user_id: Optional[int]
    table_name: str
    column_name: str
    operator: str
    filter_value: str
    is_active: int

    class Config:
        from_attributes = True


def _check_ds_admin(db: Session, datasource_id: int, user: User) -> DataSource:
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    if user.role not in ("super_admin", "org_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可管理 RLS 规则")
    if user.role == "org_admin" and ds.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="无权管理此数据源")
    return ds


@router.get("/{datasource_id}/rls", response_model=List[RLSRuleOut])
def list_rls_rules(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ds_admin(db, datasource_id, current_user)
    return db.query(RLSRule).filter(RLSRule.datasource_id == datasource_id).all()


@router.post("/{datasource_id}/rls", response_model=RLSRuleOut)
def create_rls_rule(
    datasource_id: int,
    payload: RLSRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ds_admin(db, datasource_id, current_user)
    if payload.operator not in ALLOWED_OPERATORS:
        raise HTTPException(status_code=400, detail=f"不支持的操作符: {payload.operator}")

    rule = RLSRule(
        datasource_id=datasource_id,
        org_id=payload.org_id,
        user_id=payload.user_id,
        table_name=payload.table_name,
        column_name=payload.column_name,
        operator=payload.operator,
        filter_value=payload.filter_value,
        is_active=payload.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{datasource_id}/rls/{rule_id}", response_model=RLSRuleOut)
def update_rls_rule(
    datasource_id: int,
    rule_id: int,
    payload: RLSRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ds_admin(db, datasource_id, current_user)
    rule = db.query(RLSRule).filter(RLSRule.id == rule_id, RLSRule.datasource_id == datasource_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if payload.operator and payload.operator not in ALLOWED_OPERATORS:
        raise HTTPException(status_code=400, detail=f"不支持的操作符: {payload.operator}")

    for field in ("table_name", "column_name", "operator", "filter_value", "org_id", "user_id", "is_active"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(rule, field, val)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{datasource_id}/rls/{rule_id}")
def delete_rls_rule(
    datasource_id: int,
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ds_admin(db, datasource_id, current_user)
    rule = db.query(RLSRule).filter(RLSRule.id == rule_id, RLSRule.datasource_id == datasource_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
    return {"status": "ok"}
