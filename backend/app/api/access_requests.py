from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.access_request import AccessRequest
from app.models.user import User

router = APIRouter(prefix="/access-requests", tags=["access-requests"])


class AccessRequestCreate(BaseModel):
    resource_type: str  # dataset | datasource
    resource_id: int
    resource_name: Optional[str] = None
    reason: Optional[str] = None


class AccessRequestReview(BaseModel):
    status: str  # approved | rejected
    review_comment: Optional[str] = None


class AccessRequestOut(BaseModel):
    id: int
    requester_id: int
    resource_type: str
    resource_id: int
    resource_name: Optional[str] = None
    reason: Optional[str] = None
    status: str
    reviewer_id: Optional[int] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    org_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _is_admin(user: User) -> bool:
    return user.role in ("super_admin", "org_admin")


def _scope(query, current_user: User):
    if current_user.role == "super_admin":
        return query
    return query.filter(AccessRequest.org_id == current_user.org_id)


@router.get("", response_model=List[AccessRequestOut])
def list_access_requests(
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _scope(db.query(AccessRequest), current_user)
    if mine or not _is_admin(current_user):
        q = q.filter(AccessRequest.requester_id == current_user.id)
    if status:
        q = q.filter(AccessRequest.status == status)
    if resource_type:
        q = q.filter(AccessRequest.resource_type == resource_type)
    return q.order_by(AccessRequest.created_at.desc()).all()


@router.post("", response_model=AccessRequestOut)
def create_access_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.resource_type not in ("dataset", "datasource"):
        raise HTTPException(status_code=400, detail="resource_type 必须为 dataset 或 datasource")

    existing = (
        db.query(AccessRequest)
        .filter(
            AccessRequest.requester_id == current_user.id,
            AccessRequest.resource_type == payload.resource_type,
            AccessRequest.resource_id == payload.resource_id,
            AccessRequest.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="已存在待审批的申请")

    req = AccessRequest(
        requester_id=current_user.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        resource_name=payload.resource_name,
        reason=payload.reason,
        status="pending",
        org_id=current_user.org_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.put("/{request_id}/review", response_model=AccessRequestOut)
def review_access_request(
    request_id: int,
    payload: AccessRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可审批")
    if payload.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status 必须为 approved 或 rejected")

    req = _scope(db.query(AccessRequest), current_user).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已审批")

    req.status = payload.status
    req.reviewer_id = current_user.id
    req.review_comment = payload.review_comment
    req.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    try_record_audit_log(
        db,
        actor=current_user,
        action=f"access_request.{payload.status}",
        resource_type="access_request",
        resource_id=req.id,
        resource_name=req.resource_name,
        org_id=req.org_id,
        message=f"访问申请已{('批准' if payload.status == 'approved' else '拒绝')}",
    )
    return req


@router.delete("/{request_id}")
def cancel_access_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if current_user.role != "super_admin" and req.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="无权操作")
    if req.requester_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="无权操作")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="已审批的申请无法撤销")
    db.delete(req)
    db.commit()
    return {"status": "ok"}
