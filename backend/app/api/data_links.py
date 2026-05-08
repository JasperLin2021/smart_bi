import threading
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.db.session import get_db
from app.models.data_link import DataLink, DataLinkLog, DataLinkTask
from app.models.user import User
from app.schemas.data_link import (
    DataLinkCreate, DataLinkLogOut, DataLinkOut, DataLinkTaskCreate,
    DataLinkTaskOut, DataLinkTaskUpdate, DataLinkUpdate,
)

router = APIRouter(prefix="/data-links", tags=["data-links"])

# ─── helpers ────────────────────────────────────────────────────────────────

def _scope(query, user: User):
    if user.role == "super_admin":
        return query
    return query.filter(DataLink.org_id == user.org_id)


def _task_scope(query, user: User):
    if user.role == "super_admin":
        return query
    return (
        query
        .join(DataLink, DataLinkTask.link_id == DataLink.id)
        .filter(DataLink.org_id == user.org_id)
    )


def _get_link(db: Session, link_id: int, user: User) -> DataLink:
    link = _scope(db.query(DataLink), user).filter(DataLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="连接不存在")
    return link


def _get_task(db: Session, task_id: int, user: User) -> DataLinkTask:
    task = _task_scope(db.query(DataLinkTask), user).filter(DataLinkTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

# ─── connector metadata ─────────────────────────────────────────────────────

@router.get("/connector-types")
def list_connector_types():
    from app.core.connectors.base import list_connector_types
    import app.core.connectors.jushuitan  # noqa: F401 – side-effect: register
    import app.core.connectors.yicang    # noqa: F401
    import app.core.connectors.fenxiang  # noqa: F401
    return list_connector_types()

# ─── connections ────────────────────────────────────────────────────────────

@router.get("", response_model=List[DataLinkOut])
def list_links(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _scope(db.query(DataLink), user).order_by(DataLink.updated_at.desc()).all()


@router.post("", response_model=DataLinkOut)
def create_link(
    payload: DataLinkCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_connectors_loaded()
    link = DataLink(
        name=payload.name,
        connector_type=payload.connector_type,
        config_json=payload.config_json,
        status="inactive",
        org_id=user.org_id,
        created_by=user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get("/{link_id}", response_model=DataLinkOut)
def get_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_link(db, link_id, user)


@router.put("/{link_id}", response_model=DataLinkOut)
def update_link(
    link_id: int,
    payload: DataLinkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    link = _get_link(db, link_id, user)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(link, k, v)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = _get_link(db, link_id, user)
    db.query(DataLinkTask).filter(DataLinkTask.link_id == link_id).delete()
    db.delete(link)
    db.commit()
    return {"status": "ok"}


@router.post("/{link_id}/test")
def test_link(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_connectors_loaded()
    link = _get_link(db, link_id, user)
    from app.core.connectors.base import get_connector
    connector = get_connector(link.connector_type, link.config_json or {})
    ok, msg = connector.test_connection()
    link.status = "active" if ok else "error"
    link.last_test_at = datetime.now(timezone.utc)
    link.last_test_message = msg
    db.commit()
    return {"ok": ok, "message": msg}


@router.get("/{link_id}/objects")
def list_objects(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_connectors_loaded()
    link = _get_link(db, link_id, user)
    from app.core.connectors.base import get_connector
    connector = get_connector(link.connector_type, link.config_json or {})
    return [
        {
            "name": obj.name,
            "label": obj.label,
            "description": obj.description,
            "supports_incremental": obj.supports_incremental,
            "incremental_field": obj.incremental_field,
            "fields": [
                {"name": f.name, "label": f.label, "type": f.type, "nullable": f.nullable}
                for f in obj.fields
            ],
        }
        for obj in connector.list_objects()
    ]

# ─── tasks ──────────────────────────────────────────────────────────────────

@router.get("/{link_id}/tasks", response_model=List[DataLinkTaskOut])
def list_tasks(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _get_link(db, link_id, user)
    return db.query(DataLinkTask).filter(DataLinkTask.link_id == link_id).order_by(DataLinkTask.created_at.desc()).all()


@router.post("/{link_id}/tasks", response_model=DataLinkTaskOut)
def create_task(
    link_id: int,
    payload: DataLinkTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    link = _get_link(db, link_id, user)
    task = DataLinkTask(
        link_id=link_id,
        name=payload.name,
        source_object=payload.source_object,
        target_datasource_id=payload.target_datasource_id,
        target_table=payload.target_table,
        sync_mode=payload.sync_mode,
        incremental_field=payload.incremental_field,
        field_mapping_json=payload.field_mapping_json,
        filter_json=payload.filter_json,
        cron_expression=payload.cron_expression,
        is_active=payload.is_active,
        org_id=link.org_id,
        created_by=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    if task.is_active:
        _upsert_task_job(task.id, task.cron_expression)
    return task


@router.get("/tasks/{task_id}", response_model=DataLinkTaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_task(db, task_id, user)


@router.put("/tasks/{task_id}", response_model=DataLinkTaskOut)
def update_task(
    task_id: int,
    payload: DataLinkTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task(db, task_id, user)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    if task.is_active:
        _upsert_task_job(task.id, task.cron_expression)
    else:
        _remove_task_job(task.id)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = _get_task(db, task_id, user)
    _remove_task_job(task.id)
    db.delete(task)
    db.commit()
    return {"status": "ok"}


@router.post("/tasks/{task_id}/run")
def run_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = _get_task(db, task_id, user)
    from app.core.connectors.sync_engine import run_sync_task
    t = threading.Thread(target=run_sync_task, args=(task_id,), daemon=True)
    t.start()
    try_record_audit_log(db, actor=user, action="data_link_task.run",
                         resource_type="data_link_task", resource_id=task_id,
                         resource_name=task.name, message="手动触发同步")
    return {"status": "ok", "message": "同步任务已启动"}


@router.get("/tasks/{task_id}/logs", response_model=List[DataLinkLogOut])
def get_task_logs(
    task_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_task(db, task_id, user)
    return (
        db.query(DataLinkLog)
        .filter(DataLinkLog.task_id == task_id)
        .order_by(DataLinkLog.started_at.desc())
        .limit(limit)
        .all()
    )

# ─── scheduler helpers ───────────────────────────────────────────────────────

def _ensure_connectors_loaded():
    import app.core.connectors.jushuitan  # noqa: F401
    import app.core.connectors.yicang    # noqa: F401
    import app.core.connectors.fenxiang  # noqa: F401


def _upsert_task_job(task_id: int, cron_expression: str):
    try:
        from app.core.alert_scheduler import _scheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.core.connectors.sync_engine import run_sync_task
        job_id = f"dl_task_{task_id}"
        trigger = CronTrigger.from_crontab(cron_expression)
        _scheduler.add_job(run_sync_task, trigger, args=[task_id], id=job_id, replace_existing=True)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to schedule DataLink task %d: %s", task_id, exc)


def _remove_task_job(task_id: int):
    try:
        from app.core.alert_scheduler import _scheduler
        job_id = f"dl_task_{task_id}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
    except Exception:
        pass
