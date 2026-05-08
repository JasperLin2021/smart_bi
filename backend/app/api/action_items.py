from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.message_dispatcher import MessageEvent, dispatch_message_event
from app.db.session import get_db
from app.models.action_item import ActionItem
from app.models.dashboard_config import Dashboard
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.metric import Metric
from app.models.user import User
from app.schemas.action_item import ActionItemCreate, ActionItemListResponse, ActionItemOut, ActionItemUpdate

router = APIRouter(prefix="/action-items", tags=["action-items"])
logger = logging.getLogger(__name__)

VALID_STATUSES = {"open", "in_progress", "done", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_SOURCE_TYPES = {"manual", "query", "alert", "insight", "dashboard", "dataset", "metric"}
CLOSED_STATUSES = {"done", "cancelled"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_values(status: str | None = None, priority: str | None = None, source_type: str | None = None) -> None:
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="无效行动项状态")
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="无效优先级")
    if source_type is not None and source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="无效来源类型")


def _can_access_org(user: User, org_id: int | None) -> bool:
    if user.role == "super_admin":
        return True
    return org_id == user.org_id


def _scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(ActionItem.org_id == user.org_id)
    if user.role in ("org_admin", "dept_admin"):
        return query
    return query.filter(or_(ActionItem.owner_id == user.id, ActionItem.created_by == user.id))


def _can_manage(user: User, item: ActionItem) -> bool:
    if user.role == "super_admin":
        return True
    if item.org_id != user.org_id:
        return False
    if user.role in ("org_admin", "dept_admin"):
        return True
    return item.owner_id == user.id or item.created_by == user.id


def _linked_metric_org(db: Session, metric_id: int, user: User) -> int | None:
    metric = db.query(Metric).filter(Metric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail="关联指标不存在")
    datasource = db.query(DataSource).filter(DataSource.id == metric.datasource_id).first()
    org_id = datasource.org_id if datasource else None
    if not _can_access_org(user, org_id):
        raise HTTPException(status_code=403, detail="无权访问关联指标")
    return org_id


def _linked_dataset_org(db: Session, dataset_id: int, user: User) -> int | None:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="关联数据集不存在")
    if not _can_access_org(user, dataset.org_id):
        raise HTTPException(status_code=403, detail="无权访问关联数据集")
    return dataset.org_id


def _linked_dashboard_org(db: Session, dashboard_id: int, user: User) -> int | None:
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="关联看板不存在")
    if not _can_access_org(user, dashboard.org_id):
        raise HTTPException(status_code=403, detail="无权访问关联看板")
    return dashboard.org_id


def _resolve_org_id(
    db: Session,
    current_user: User,
    *,
    requested_org_id: int | None = None,
    linked_metric_id: int | None = None,
    linked_dataset_id: int | None = None,
    linked_dashboard_id: int | None = None,
) -> int | None:
    org_id = requested_org_id if current_user.role == "super_admin" and requested_org_id is not None else current_user.org_id
    linked_orgs = [
        _linked_metric_org(db, linked_metric_id, current_user) if linked_metric_id else None,
        _linked_dataset_org(db, linked_dataset_id, current_user) if linked_dataset_id else None,
        _linked_dashboard_org(db, linked_dashboard_id, current_user) if linked_dashboard_id else None,
    ]
    for linked_org_id in linked_orgs:
        if linked_org_id is None:
            continue
        if org_id is None:
            org_id = linked_org_id
        elif org_id != linked_org_id:
            raise HTTPException(status_code=400, detail="行动项组织与关联资源不一致")
    return org_id


def _get_item_for_user(db: Session, item_id: int, user: User) -> ActionItem:
    item = _scope(db.query(ActionItem), user).filter(ActionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="行动项不存在")
    return item


def _unique_user_ids(values: list[int | None]) -> list[int]:
    result: list[int] = []
    for value in values:
        if value is None or value in result:
            continue
        result.append(value)
    return result


def _safe_dispatch_action_item_event(db: Session, event: MessageEvent) -> None:
    if not event.recipient_user_ids:
        return
    try:
        dispatch_message_event(db, event)
    except Exception as exc:
        logger.error("Action item message dispatch failed: %s", exc)


@router.get("", response_model=ActionItemListResponse)
def list_action_items(
    status: str | None = None,
    source_type: str | None = None,
    owner_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_values(status=status, source_type=source_type)
    query = _scope(db.query(ActionItem), current_user)
    if status:
        query = query.filter(ActionItem.status == status)
    if source_type:
        query = query.filter(ActionItem.source_type == source_type)
    if owner_id:
        query = query.filter(ActionItem.owner_id == owner_id)
    if q:
        query = query.filter(ActionItem.title.ilike(f"%{q}%"))
    items = query.order_by(ActionItem.updated_at.desc(), ActionItem.id.desc()).all()
    return {"items": items, "total": len(items)}


@router.post("", response_model=ActionItemOut)
def create_action_item(
    payload: ActionItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_values(status=payload.status, priority=payload.priority, source_type=payload.source_type)
    org_id = _resolve_org_id(
        db,
        current_user,
        requested_org_id=payload.org_id,
        linked_metric_id=payload.linked_metric_id,
        linked_dataset_id=payload.linked_dataset_id,
        linked_dashboard_id=payload.linked_dashboard_id,
    )
    item = ActionItem(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        created_by=current_user.id,
        owner_id=payload.owner_id or current_user.id,
        closed_at=_utcnow() if payload.status in CLOSED_STATUSES else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    try_record_audit_log(
        db,
        actor=current_user,
        action="action_item.create",
        resource_type="action_item",
        resource_id=item.id,
        resource_name=item.title,
        org_id=item.org_id,
        message="行动项已创建",
        detail={"source_type": item.source_type, "source_id": item.source_id},
    )
    _safe_dispatch_action_item_event(
        db,
        MessageEvent(
            event_type="action_item.assigned",
            org_id=item.org_id,
            recipient_user_ids=_unique_user_ids([item.owner_id]),
            title=f"行动项：{item.title}",
            content=item.description or "你有一个新的行动项需要处理。",
            link_url="/action-items",
        ),
    )
    return item


@router.get("/{item_id}", response_model=ActionItemOut)
def get_action_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_item_for_user(db, item_id, current_user)


@router.put("/{item_id}", response_model=ActionItemOut)
def update_action_item(
    item_id: int,
    payload: ActionItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_for_user(db, item_id, current_user)
    if not _can_manage(current_user, item):
        raise HTTPException(status_code=403, detail="无权限")
    previous_status = item.status
    values = payload.model_dump(exclude_unset=True)
    _ensure_values(
        status=values.get("status"),
        priority=values.get("priority"),
        source_type=values.get("source_type"),
    )
    if any(key in values for key in ("org_id", "linked_metric_id", "linked_dataset_id", "linked_dashboard_id")):
        values["org_id"] = _resolve_org_id(
            db,
            current_user,
            requested_org_id=values.get("org_id", item.org_id),
            linked_metric_id=values.get("linked_metric_id", item.linked_metric_id),
            linked_dataset_id=values.get("linked_dataset_id", item.linked_dataset_id),
            linked_dashboard_id=values.get("linked_dashboard_id", item.linked_dashboard_id),
    )
    if "status" in values:
        item.closed_at = _utcnow() if values["status"] in CLOSED_STATUSES else None
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    try_record_audit_log(
        db,
        actor=current_user,
        action="action_item.update",
        resource_type="action_item",
        resource_id=item.id,
        resource_name=item.title,
        org_id=item.org_id,
        message="行动项已更新",
        detail={"fields": list(values.keys())},
    )
    if "status" in values and values["status"] != previous_status:
        _safe_dispatch_action_item_event(
            db,
            MessageEvent(
                event_type="action_item.status_changed",
                org_id=item.org_id,
                recipient_user_ids=_unique_user_ids([item.owner_id, item.created_by]),
                title=f"行动项状态变更：{item.title}",
                content=f"行动项状态已从 {previous_status} 变更为 {item.status}。",
                link_url="/action-items",
            ),
        )
    return item


@router.delete("/{item_id}")
def delete_action_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_for_user(db, item_id, current_user)
    if not _can_manage(current_user, item):
        raise HTTPException(status_code=403, detail="无权限")
    resource_name = item.title
    org_id = item.org_id
    db.delete(item)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="action_item.delete",
        resource_type="action_item",
        resource_id=item_id,
        resource_name=resource_name,
        org_id=org_id,
        message="行动项已删除",
    )
    return {"status": "ok"}
