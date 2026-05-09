from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.audit import try_record_audit_log
from app.core.permissions import require_action
from app.db.session import get_db
from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineOut,
    PipelineRunOut,
    PipelineRunRequest,
    PipelineUpdate,
    QualityRuleCreate,
    QualityRuleOut,
    QualityRuleUpdate,
)

router = APIRouter(tags=["pipelines"])

VALID_PIPELINE_STATUSES = {"draft", "active", "paused", "archived"}
VALID_RUN_MODES = {"manual", "scheduled", "incremental", "full", "backfill"}
VALID_RULE_TYPES = {"not_null", "unique", "range", "regex", "row_count", "freshness", "custom_sql"}


def _dataset_scope(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))


def _get_dataset_for_user(db: Session, dataset_id: int, user: User) -> Dataset:
    dataset = _dataset_scope(db.query(Dataset), user).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _pipeline_scope(query, user: User):
    if user.role == "super_admin":
        return query
    return query.filter(DataPipeline.org_id == user.org_id)


def _get_pipeline_for_user(db: Session, pipeline_id: int, user: User) -> DataPipeline:
    pipeline = _pipeline_scope(db.query(DataPipeline), user).filter(DataPipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="数据集成管道不存在")
    return pipeline


def _validate_dag(dag_json: dict[str, Any]) -> None:
    nodes = dag_json.get("nodes")
    edges = dag_json.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        raise HTTPException(status_code=400, detail="DAG 至少需要一个节点")
    if not isinstance(edges, list):
        raise HTTPException(status_code=400, detail="DAG 边必须为数组")
    node_ids = {str(node.get("id")) for node in nodes if isinstance(node, dict) and node.get("id")}
    if len(node_ids) != len(nodes):
        raise HTTPException(status_code=400, detail="DAG 节点需要唯一 ID")
    for edge in edges:
        if not isinstance(edge, dict) or str(edge.get("source")) not in node_ids or str(edge.get("target")) not in node_ids:
            raise HTTPException(status_code=400, detail="DAG 边引用了不存在的节点")


def _node_logs_for(pipeline: DataPipeline) -> dict[str, Any]:
    dag = pipeline.dag_json or {}
    nodes = dag.get("nodes", [])
    logs = []
    for index, node in enumerate(nodes, start=1):
        logs.append(
            {
                "node_id": node.get("id"),
                "label": node.get("label") or node.get("id"),
                "type": node.get("type") or "task",
                "status": "success",
                "records": 100 * index,
            }
        )
    return {
        "nodes": logs,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(dag.get("edges", [])),
            "quality": "passed",
        },
    }


@router.get("/pipelines", response_model=list[PipelineOut])
def list_pipelines(
    dataset_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    query = _pipeline_scope(db.query(DataPipeline), current_user)
    if dataset_id:
        query = query.filter(DataPipeline.dataset_id == dataset_id)
    return query.order_by(DataPipeline.updated_at.desc()).all()


@router.post("/pipelines", response_model=PipelineOut)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.create")
    if payload.status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(status_code=400, detail="无效管道状态")
    if payload.run_mode not in VALID_RUN_MODES:
        raise HTTPException(status_code=400, detail="无效运行模式")
    _validate_dag(payload.dag_json)
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    pipeline = DataPipeline(
        **payload.model_dump(),
        org_id=dataset.org_id,
        owner_id=getattr(current_user, "id", None),
        created_by=getattr(current_user, "id", None),
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    try_record_audit_log(
        db,
        actor=current_user,
        action="pipeline.create",
        resource_type="data_pipeline",
        resource_id=pipeline.id,
        resource_name=pipeline.name,
        org_id=pipeline.org_id,
        message="数据集成管道已创建",
        detail={"dataset_id": pipeline.dataset_id},
    )
    return pipeline


@router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    return _get_pipeline_for_user(db, pipeline_id, current_user)


@router.put("/pipelines/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: int,
    payload: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.update")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] not in VALID_PIPELINE_STATUSES:
        raise HTTPException(status_code=400, detail="无效管道状态")
    if "run_mode" in updates and updates["run_mode"] not in VALID_RUN_MODES:
        raise HTTPException(status_code=400, detail="无效运行模式")
    if "dag_json" in updates:
        _validate_dag(updates["dag_json"])
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        pipeline.org_id = dataset.org_id
    for key, value in updates.items():
        setattr(pipeline, key, value)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.delete("/pipelines/{pipeline_id}")
def delete_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.delete")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    name = pipeline.name
    db.query(DataPipelineRun).filter(DataPipelineRun.pipeline_id == pipeline_id).delete()
    db.query(DataQualityRule).filter(DataQualityRule.pipeline_id == pipeline_id).delete()
    db.delete(pipeline)
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="pipeline.delete",
        resource_type="data_pipeline",
        resource_id=pipeline_id,
        resource_name=name,
        message="数据集成管道已删除",
    )
    return {"status": "ok"}


@router.post("/pipelines/{pipeline_id}/run", response_model=PipelineRunOut)
def run_pipeline(
    pipeline_id: int,
    payload: PipelineRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.run")
    if payload.mode not in VALID_RUN_MODES:
        raise HTTPException(status_code=400, detail="无效运行模式")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    now = datetime.now(timezone.utc)
    node_logs = _node_logs_for(pipeline)
    run = DataPipelineRun(
        pipeline_id=pipeline.id,
        mode=payload.mode,
        status="success",
        reason=payload.reason,
        node_logs_json=node_logs,
        records_read=sum(item["records"] for item in node_logs["nodes"]),
        records_written=sum(item["records"] for item in node_logs["nodes"]),
        records_failed=0,
        org_id=pipeline.org_id,
        triggered_by_id=getattr(current_user, "id", None),
        finished_at=now,
    )
    pipeline.last_run_status = "success"
    pipeline.last_run_at = now
    pipeline.status = "active" if pipeline.status == "draft" else pipeline.status
    db.add(run)
    db.commit()
    db.refresh(run)
    try_record_audit_log(
        db,
        actor=current_user,
        action="pipeline.run",
        resource_type="data_pipeline",
        resource_id=pipeline.id,
        resource_name=pipeline.name,
        org_id=pipeline.org_id,
        message="数据集成管道已运行",
        detail={"mode": payload.mode, "run_id": run.id},
    )
    return run


@router.get("/pipelines/{pipeline_id}/runs", response_model=list[PipelineRunOut])
def list_pipeline_runs(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    _get_pipeline_for_user(db, pipeline_id, current_user)
    return (
        db.query(DataPipelineRun)
        .filter(DataPipelineRun.pipeline_id == pipeline_id)
        .order_by(DataPipelineRun.started_at.desc())
        .limit(100)
        .all()
    )


@router.get("/quality-rules", response_model=list[QualityRuleOut])
def list_quality_rules(
    dataset_id: int | None = None,
    pipeline_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    query = db.query(DataQualityRule)
    if current_user.role != "super_admin":
        query = query.filter(DataQualityRule.org_id == current_user.org_id)
    if dataset_id:
        query = query.filter(DataQualityRule.dataset_id == dataset_id)
    if pipeline_id:
        query = query.filter(DataQualityRule.pipeline_id == pipeline_id)
    return query.order_by(DataQualityRule.created_at.desc()).all()


@router.post("/quality-rules", response_model=QualityRuleOut)
def create_quality_rule(
    payload: QualityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "quality_rule.create")
    if payload.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(status_code=400, detail="无效质量规则类型")
    dataset = _get_dataset_for_user(db, payload.dataset_id, current_user)
    if payload.pipeline_id:
        pipeline = _get_pipeline_for_user(db, payload.pipeline_id, current_user)
        if pipeline.dataset_id != payload.dataset_id:
            raise HTTPException(status_code=400, detail="质量规则的数据集必须与管道一致")
    rule = DataQualityRule(
        **payload.model_dump(),
        org_id=dataset.org_id,
        created_by=getattr(current_user, "id", None),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/quality-rules/{rule_id}", response_model=QualityRuleOut)
def update_quality_rule(
    rule_id: int,
    payload: QualityRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "quality_rule.update")
    query = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id)
    if current_user.role != "super_admin":
        query = query.filter(DataQualityRule.org_id == current_user.org_id)
    rule = query.first()
    if not rule:
        raise HTTPException(status_code=404, detail="质量规则不存在")
    updates = payload.model_dump(exclude_unset=True)
    if "rule_type" in updates and updates["rule_type"] not in VALID_RULE_TYPES:
        raise HTTPException(status_code=400, detail="无效质量规则类型")
    for key, value in updates.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule
