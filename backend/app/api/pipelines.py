from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.datasets import _execute_dataset_extract, _get_datasource_for_user as _get_datasource_for_user
from app.core.audit import try_record_audit_log
from app.core.etl_executor import execute_pipeline_dag
from app.core.excel_executor import execute_excel_query
from app.core.permissions import require_action
from app.db.session import get_db
from app.db.session import get_datasource_engine
from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataPipelineVersion, DataQualityRule
from app.models.dataset import Dataset, DatasetRefreshLog
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineDiagnostic,
    PipelineLineageOut,
    PipelineOut,
    PipelinePreviewOut,
    PipelinePreviewRequest,
    PipelineRunOut,
    PipelineRunRequest,
    PipelineUpdate,
    PipelineValidationOut,
    PipelineVersionOut,
    QualityRuleCreate,
    QualityRuleOut,
    QualityRuleUpdate,
)

router = APIRouter(tags=["pipelines"])

VALID_PIPELINE_STATUSES = {"draft", "active", "paused", "archived"}
VALID_RUN_MODES = {"manual", "scheduled", "incremental", "full", "backfill"}
VALID_RULE_TYPES = {"not_null", "unique", "range", "regex", "row_count", "freshness", "custom_sql"}
VALID_PIPELINE_ENVIRONMENTS = {"dev", "test", "prod"}
VALID_PIPELINE_PRIORITIES = {"low", "medium", "high", "critical"}
ALLOWED_DAG_NODE_TYPES = {"source", "extract", "metadata_extract", "transform", "join", "union", "quality", "load", "sink"}
FAN_IN_NODE_TYPES = {"join", "union"}
SOURCE_NODE_TYPES = {"source", "extract", "metadata_extract"}


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


def _cron_is_valid(expression: str | None) -> bool:
    if not expression or not expression.strip():
        return False
    parts = expression.strip().split()
    if len(parts) != 5:
        return False
    allowed = set("0123456789*,-/")
    return all(part and set(part) <= allowed for part in parts)


def _diagnose_dag(dag_json: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    nodes = dag_json.get("nodes")
    edges = dag_json.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        return [{"severity": "critical", "code": "empty_dag", "message": "DAG 至少需要一个节点"}]
    if not isinstance(edges, list):
        return [{"severity": "critical", "code": "invalid_edges", "message": "DAG 边必须为数组"}]

    node_ids: set[str] = set()
    node_types: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            diagnostics.append({"severity": "critical", "code": "missing_node_id", "message": "DAG 节点需要唯一 ID"})
            continue
        node_id = str(node.get("id"))
        if node_id in node_ids:
            diagnostics.append({"severity": "critical", "code": "duplicate_node_id", "message": f"节点 {node_id} 重复", "node_id": node_id})
            continue
        node_ids.add(node_id)
        node_type = str(node.get("type") or "task")
        node_types[node_id] = node_type
        if node_type not in ALLOWED_DAG_NODE_TYPES:
            diagnostics.append({"severity": "critical", "code": "invalid_node_type", "message": f"节点 {node_id} 类型无效", "node_id": node_id})

    if len(node_ids) != len(nodes):
        diagnostics.append({"severity": "critical", "code": "duplicate_node_count", "message": "DAG 节点需要唯一 ID"})

    adjacency = {node_id: [] for node_id in node_ids}
    in_degree = {node_id: 0 for node_id in node_ids}
    out_degree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict) or str(edge.get("source")) not in node_ids or str(edge.get("target")) not in node_ids:
            diagnostics.append({"severity": "critical", "code": "missing_edge_node", "message": "DAG 边引用了不存在的节点"})
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source == target:
            diagnostics.append({"severity": "critical", "code": "self_loop", "message": f"节点 {source} 不能依赖自身", "node_id": source})
            continue
        adjacency[source].append(target)
        out_degree[source] += 1
        in_degree[target] += 1

    for node_id in sorted(node_ids):
        node_type = node_types.get(node_id)
        if in_degree[node_id] > 1 and node_type not in FAN_IN_NODE_TYPES:
            diagnostics.append(
                {
                    "severity": "critical",
                    "code": "invalid_fan_in",
                    "message": f"节点 {node_id} 有多个上游时必须使用 join 或 union 显式汇合",
                    "node_id": node_id,
                }
            )
        if node_type == "join" and in_degree[node_id] != 2:
            diagnostics.append(
                {
                    "severity": "critical",
                    "code": "invalid_join_inputs",
                    "message": f"join 节点 {node_id} 必须连接两个上游",
                    "node_id": node_id,
                }
            )
        if node_type == "union" and in_degree[node_id] < 2:
            diagnostics.append(
                {
                    "severity": "critical",
                    "code": "invalid_union_inputs",
                    "message": f"union 节点 {node_id} 至少需要两个上游",
                    "node_id": node_id,
                }
            )

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        if node_type == "join" and not (config.get("left_key") or config.get("key")):
            diagnostics.append({"severity": "critical", "code": "missing_join_key", "message": f"join 节点 {node_id} 缺少关联键", "node_id": node_id})
        if node_type == "metadata_extract" and config.get("datasource_id") is None:
            diagnostics.append({"severity": "warning", "code": "metadata_datasource_default", "message": f"元数据节点 {node_id} 将使用管道默认数据源", "node_id": node_id})

    if not any(node_type in SOURCE_NODE_TYPES for node_type in node_types.values()):
        diagnostics.append({"severity": "critical", "code": "missing_extract", "message": "企业 ETL DAG 必须包含抽取/源节点"})
    if not any(node_type in {"load", "sink"} for node_type in node_types.values()):
        diagnostics.append({"severity": "critical", "code": "missing_load", "message": "企业 ETL DAG 必须包含装载/目标节点"})
    if not any(node_type == "quality" for node_type in node_types.values()):
        diagnostics.append({"severity": "warning", "code": "missing_quality_gate", "message": "建议增加质量闸门节点，避免脏数据进入目标数据集"})

    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for target_id in adjacency.get(node_id, []):
            if visit(target_id):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    if any(visit(node_id) for node_id in node_ids):
        diagnostics.append({"severity": "critical", "code": "cycle", "message": "DAG 不允许形成循环依赖"})

    if len(node_ids) > 1:
        isolated = [node_id for node_id in node_ids if in_degree[node_id] == 0 and out_degree[node_id] == 0]
        for node_id in isolated:
            diagnostics.append({"severity": "warning", "code": "isolated_node", "message": f"节点 {node_id} 未连接到主链路", "node_id": node_id})

    return diagnostics


def _critical_messages(diagnostics: list[dict[str, Any]]) -> list[str]:
    return [str(item["message"]) for item in diagnostics if item.get("severity") == "critical"]


def _validate_dag(dag_json: dict[str, Any]) -> None:
    diagnostics = _diagnose_dag(dag_json)
    critical = _critical_messages(diagnostics)
    if critical:
        raise HTTPException(status_code=400, detail="；".join(critical))


def _validate_pipeline_settings(
    run_mode: str,
    schedule_cron: str | None,
    environment: str,
    priority: str,
    sla_minutes: int,
    retry_count: int,
    timeout_minutes: int,
) -> None:
    if run_mode not in VALID_RUN_MODES:
        raise HTTPException(status_code=400, detail="无效运行模式")
    if environment not in VALID_PIPELINE_ENVIRONMENTS:
        raise HTTPException(status_code=400, detail="无效运行环境")
    if priority not in VALID_PIPELINE_PRIORITIES:
        raise HTTPException(status_code=400, detail="无效管道优先级")
    if run_mode == "scheduled" and not _cron_is_valid(schedule_cron):
        raise HTTPException(status_code=400, detail="调度模式需要有效 Cron 表达式")
    if schedule_cron and not _cron_is_valid(schedule_cron):
        raise HTTPException(status_code=400, detail="Cron 表达式格式无效")
    if sla_minutes <= 0 or timeout_minutes <= 0:
        raise HTTPException(status_code=400, detail="SLA 和超时时间必须大于 0")
    if retry_count < 0 or retry_count > 10:
        raise HTTPException(status_code=400, detail="重试次数必须在 0 到 10 之间")


def _pipeline_value(pipeline: DataPipeline, name: str, default: Any) -> Any:
    value = getattr(pipeline, name, None)
    return default if value is None else value


def _pipeline_diagnostics(pipeline: DataPipeline, active_rule_count: int = 0) -> list[dict[str, Any]]:
    diagnostics = _diagnose_dag(pipeline.dag_json or {})
    schedule_cron = _pipeline_value(pipeline, "schedule_cron", None)
    run_mode = _pipeline_value(pipeline, "run_mode", "manual")
    environment = _pipeline_value(pipeline, "environment", "prod")
    priority = _pipeline_value(pipeline, "priority", "medium")
    sla_minutes = int(_pipeline_value(pipeline, "sla_minutes", 120))
    retry_count = int(_pipeline_value(pipeline, "retry_count", 2))
    timeout_minutes = int(_pipeline_value(pipeline, "timeout_minutes", 60))

    try:
        _validate_pipeline_settings(run_mode, schedule_cron, environment, priority, sla_minutes, retry_count, timeout_minutes)
    except HTTPException as exc:
        diagnostics.append({"severity": "critical", "code": "invalid_settings", "message": str(exc.detail)})

    if active_rule_count <= 0:
        diagnostics.append({"severity": "warning", "code": "missing_quality_rules", "message": "尚未启用数据质量规则，上线前建议至少配置关键字段非空或行数波动规则"})
    if priority in {"high", "critical"} and not (_pipeline_value(pipeline, "alert_policy_json", None) or {}).get("on_failure"):
        diagnostics.append({"severity": "warning", "code": "missing_failure_alert", "message": "高优先级管道建议开启失败告警"})
    return diagnostics


def _build_dataset_resolver(db: Session, current_user: User):
    def resolve(dataset_id: int) -> tuple[Dataset, DataSource]:
        source_dataset = _get_dataset_for_user(db, dataset_id, current_user)
        source_datasource = _get_datasource_for_user(db, source_dataset.datasource_id, current_user)
        return source_dataset, source_datasource

    return resolve


def _build_datasource_resolver(db: Session, current_user: User):
    def resolve(datasource_id: int) -> DataSource:
        return _get_datasource_for_user(db, datasource_id, current_user)

    return resolve


def _sync_pipeline_schedule(pipeline_id: int) -> None:
    try:
        from app.core.alert_scheduler import upsert_pipeline_job

        upsert_pipeline_job(pipeline_id)
    except Exception:
        pass


def _remove_pipeline_schedule(pipeline_id: int) -> None:
    try:
        from app.core.alert_scheduler import remove_pipeline_job

        remove_pipeline_job(pipeline_id)
    except Exception:
        pass


def _dispatch_pipeline_notifications(db: Session, pipeline: DataPipeline, run: DataPipelineRun, current_user: User) -> dict[str, str]:
    policy = pipeline.alert_policy_json if isinstance(pipeline.alert_policy_json, dict) else {}
    should_notify = False
    if run.status == "failed" and policy.get("on_failure"):
        should_notify = True
    if run.records_failed and policy.get("on_quality_failure", True):
        should_notify = True
    if run.duration_ms and pipeline.sla_minutes and run.duration_ms > int(pipeline.sla_minutes) * 60 * 1000 and policy.get("on_sla_miss", True):
        should_notify = True
    if not should_notify:
        return {}

    notify_result: dict[str, str] = {}
    recipient_ids = policy.get("recipient_user_ids") if isinstance(policy.get("recipient_user_ids"), list) else []
    if not recipient_ids and pipeline.owner_id:
        recipient_ids = [pipeline.owner_id]
    if not recipient_ids and getattr(current_user, "id", None):
        recipient_ids = [current_user.id]
    if recipient_ids:
        try:
            from app.core.message_dispatcher import MessageEvent, dispatch_message_event

            dispatch_message_event(
                db,
                MessageEvent(
                    event_type="pipeline.run_failed" if run.status == "failed" else "pipeline.quality_failed",
                    org_id=pipeline.org_id,
                    recipient_user_ids=[int(item) for item in recipient_ids],
                    title=f"[Smart BI 管道] {pipeline.name} {run.status}",
                    content=run.error_message or f"管道 {pipeline.name} 运行状态: {run.status}",
                    link_url="/data-pipelines",
                ),
            )
            notify_result["wechat_app"] = "queued"
        except Exception as exc:
            notify_result["wechat_app"] = f"error: {exc}"
    return notify_result


def _build_validation_result(pipeline: DataPipeline, diagnostics: list[dict[str, Any]]) -> PipelineValidationOut:
    critical_count = len([item for item in diagnostics if item.get("severity") == "critical"])
    warning_count = len([item for item in diagnostics if item.get("severity") == "warning"])
    dag = pipeline.dag_json or {}
    status = "blocked" if critical_count else "warning" if warning_count else "ready"
    return PipelineValidationOut(
        status=status,
        diagnostics=[PipelineDiagnostic(**item) for item in diagnostics],
        critical_count=critical_count,
        warning_count=warning_count,
        node_count=len(dag.get("nodes", []) or []),
        edge_count=len(dag.get("edges", []) or []),
        schedule_cron=_pipeline_value(pipeline, "schedule_cron", None),
        run_mode=_pipeline_value(pipeline, "run_mode", "manual"),
        environment=_pipeline_value(pipeline, "environment", "prod"),
        priority=_pipeline_value(pipeline, "priority", "medium"),
        sla_minutes=int(_pipeline_value(pipeline, "sla_minutes", 120)),
        retry_count=int(_pipeline_value(pipeline, "retry_count", 2)),
        timeout_minutes=int(_pipeline_value(pipeline, "timeout_minutes", 60)),
    )


def _row_value(row: dict[str, Any], field: str | None) -> Any:
    if not field:
        return None
    candidates = [field, field.split(".")[-1]]
    lower_map = {str(key).lower(): key for key in row.keys()}
    for candidate in candidates:
        if candidate in row:
            return row[candidate]
        key = lower_map.get(candidate.lower())
        if key is not None:
            return row[key]
    return None


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_float(value: Any) -> float | None:
    if _is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare_number(actual: float, operator: str | None, expected: float) -> bool:
    op = (operator or "gte").lower()
    if op in {"eq", "=", "=="}:
        return actual == expected
    if op in {"gt", ">"}:
        return actual > expected
    if op in {"gte", ">=", "min"}:
        return actual >= expected
    if op in {"lt", "<"}:
        return actual < expected
    if op in {"lte", "<=", "max"}:
        return actual <= expected
    return actual >= expected


def _parse_range_threshold(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    parts = [item.strip() for item in re.split(r"[,，~]", value) if item.strip()]
    if len(parts) != 2:
        return None
    left = _to_float(parts[0])
    right = _to_float(parts[1])
    if left is None or right is None:
        return None
    return (left, right)


def _parse_freshness_delta(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([mhd])\s*$", value, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"m": 60, "h": 3600, "d": 86400}[unit]
    return amount * multiplier


def _parse_datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if _is_blank(value):
        return None
    text_value = str(value).strip().replace("Z", "+00:00")
    for candidate in (text_value, text_value.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _custom_sql_violation_count(rule: DataQualityRule, datasource: DataSource) -> int:
    sql = (rule.threshold or "").strip()
    if not sql or not sql.lower().startswith("select"):
        return 1
    if datasource.source_type == "excel":
        result = execute_excel_query(datasource.database_url, sql)
        rows = result.get("rows", [])
        if not rows:
            return 0
        first_row = rows[0]
        first_value = next(iter(first_row.values())) if isinstance(first_row, dict) and first_row else 0
    else:
        engine = get_datasource_engine(datasource.database_url)
        with engine.connect() as conn:
            row = conn.execute(text(sql)).first()
        first_value = row[0] if row else 0
    numeric = _to_float(first_value)
    if numeric is None:
        return 0 if bool(first_value) else 1
    return int(numeric)


def _evaluate_quality_rule(rule: DataQualityRule, rows: list[dict[str, Any]], datasource: DataSource) -> dict[str, Any]:
    failed_count = 0
    message = ""
    rule_type = rule.rule_type
    field_label = rule.field or "记录数"

    if rule_type == "not_null":
        failed_count = sum(1 for row in rows if _is_blank(_row_value(row, rule.field)))
        message = f"{field_label} 存在 {failed_count} 条空值"
    elif rule_type == "unique":
        seen: set[Any] = set()
        duplicates = 0
        for row in rows:
            value = _row_value(row, rule.field)
            if _is_blank(value):
                continue
            if value in seen:
                duplicates += 1
            seen.add(value)
        failed_count = duplicates
        message = f"{field_label} 存在 {failed_count} 条重复值"
    elif rule_type == "range":
        bounds = _parse_range_threshold(rule.threshold)
        if not bounds:
            failed_count = 1
            message = f"{rule.name} 范围阈值格式无效"
        else:
            lower, upper = bounds
            failed_count = sum(
                1
                for row in rows
                if (value := _to_float(_row_value(row, rule.field))) is None or value < lower or value > upper
            )
            message = f"{field_label} 超出 {lower:g}~{upper:g} 范围 {failed_count} 条"
    elif rule_type == "regex":
        try:
            pattern = re.compile(rule.threshold or "")
            failed_count = sum(
                1
                for row in rows
                if not _is_blank(value := _row_value(row, rule.field)) and not pattern.search(str(value))
            )
            message = f"{field_label} 正则不匹配 {failed_count} 条"
        except re.error as exc:
            failed_count = 1
            message = f"{rule.name} 正则表达式无效: {exc}"
    elif rule_type == "row_count":
        expected = _to_float(rule.threshold)
        if expected is None:
            failed_count = 1
            message = f"{rule.name} 行数阈值无效"
        else:
            passed = _compare_number(float(len(rows)), rule.operator, expected)
            failed_count = 0 if passed else 1
            message = f"实际行数 {len(rows)} 未满足 {rule.operator or 'gte'} {expected:g}"
    elif rule_type == "freshness":
        delta_seconds = _parse_freshness_delta(rule.threshold)
        values = [_parse_datetime_value(_row_value(row, rule.field)) for row in rows]
        valid_values = [value for value in values if value is not None]
        if delta_seconds is None or not valid_values:
            failed_count = 1
            message = f"{rule.name} 新鲜度阈值或时间字段无效"
        else:
            age_seconds = (datetime.now(timezone.utc) - max(valid_values)).total_seconds()
            failed_count = 0 if age_seconds <= delta_seconds else 1
            message = f"{field_label} 最新数据延迟 {int(age_seconds)} 秒"
    elif rule_type == "custom_sql":
        failed_count = _custom_sql_violation_count(rule, datasource)
        message = f"{rule.name} 自定义 SQL 返回 {failed_count} 条异常"
    else:
        failed_count = 1
        message = f"不支持的质量规则类型: {rule_type}"

    if failed_count <= 0:
        status = "passed"
        message = f"{rule.name} 通过"
    else:
        status = "failed" if rule.severity == "error" else "warning"
    return {
        "rule_id": rule.id,
        "name": rule.name,
        "type": rule.rule_type,
        "field": rule.field,
        "severity": rule.severity,
        "status": status,
        "failed_count": failed_count,
        "message": message,
    }


def _evaluate_quality_rules(
    rules: list[DataQualityRule],
    rows: list[dict[str, Any]],
    datasource: DataSource,
    checked_at: datetime,
) -> list[dict[str, Any]]:
    results = []
    for rule in rules:
        result = _evaluate_quality_rule(rule, rows, datasource)
        rule.last_status = result["status"]
        rule.last_checked_at = checked_at
        results.append(result)
    return results


def _node_logs_for(
    pipeline: DataPipeline,
    payload: PipelineRunRequest,
    row_count: int,
    quality_results: list[dict[str, Any]],
) -> dict[str, Any]:
    dag = pipeline.dag_json or {}
    nodes = dag.get("nodes", [])
    logs = []
    quality_failed = any(result["status"] == "failed" for result in quality_results)
    quality_warning = any(result["status"] == "warning" for result in quality_results)
    quality_status = "failed" if quality_failed else "warning" if quality_warning else "passed"
    failed_records = sum(result["failed_count"] for result in quality_results if result["status"] == "failed")
    for index, node in enumerate(nodes, start=1):
        node_type = node.get("type") or "task"
        node_status = "success"
        read_count = row_count
        written_count = row_count
        node_failed = 0
        if node_type == "quality":
            node_status = "failed" if quality_failed else "warning" if quality_warning else "success"
            node_failed = failed_records
            written_count = 0 if quality_failed else row_count
        elif node_type in {"load", "sink"}:
            if quality_failed:
                node_status = "skipped"
                read_count = 0
                written_count = 0
            elif payload.dry_run:
                written_count = 0
        logs.append(
            {
                "node_id": node.get("id"),
                "label": node.get("label") or node.get("id"),
                "type": node_type,
                "status": node_status,
                "records_read": read_count,
                "records_written": written_count,
                "records_failed": node_failed,
                "duration_ms": 240 + index * 95,
                "quality_rules_checked": len(quality_results) if node_type == "quality" else 0,
            }
        )
    run_window = {
        "start": payload.window_start.isoformat() if payload.window_start else None,
        "end": payload.window_end.isoformat() if payload.window_end else None,
    }
    return {
        "nodes": logs,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(dag.get("edges", [])),
            "source_row_count": row_count,
            "quality": quality_status,
            "quality_results": quality_results,
            "dry_run": payload.dry_run,
            "run_window": run_window,
            "retry_count": int(_pipeline_value(pipeline, "retry_count", 2)),
            "timeout_minutes": int(_pipeline_value(pipeline, "timeout_minutes", 60)),
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
    _validate_pipeline_settings(
        payload.run_mode,
        payload.schedule_cron,
        payload.environment,
        payload.priority,
        payload.sla_minutes,
        payload.retry_count,
        payload.timeout_minutes,
    )
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
    _sync_pipeline_schedule(pipeline.id)
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
    candidate = {
        "run_mode": updates.get("run_mode", _pipeline_value(pipeline, "run_mode", "manual")),
        "schedule_cron": updates.get("schedule_cron", _pipeline_value(pipeline, "schedule_cron", None)),
        "environment": updates.get("environment", _pipeline_value(pipeline, "environment", "prod")),
        "priority": updates.get("priority", _pipeline_value(pipeline, "priority", "medium")),
        "sla_minutes": updates.get("sla_minutes", int(_pipeline_value(pipeline, "sla_minutes", 120))),
        "retry_count": updates.get("retry_count", int(_pipeline_value(pipeline, "retry_count", 2))),
        "timeout_minutes": updates.get("timeout_minutes", int(_pipeline_value(pipeline, "timeout_minutes", 60))),
    }
    _validate_pipeline_settings(**candidate)
    if "dag_json" in updates:
        _validate_dag(updates["dag_json"])
    if "dataset_id" in updates:
        dataset = _get_dataset_for_user(db, updates["dataset_id"], current_user)
        pipeline.org_id = dataset.org_id
    for key, value in updates.items():
        setattr(pipeline, key, value)
    db.commit()
    db.refresh(pipeline)
    _sync_pipeline_schedule(pipeline.id)
    return pipeline


@router.post("/pipelines/{pipeline_id}/validate", response_model=PipelineValidationOut)
def validate_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    active_rule_count = (
        db.query(DataQualityRule)
        .filter(
            DataQualityRule.pipeline_id == pipeline.id,
            DataQualityRule.dataset_id == pipeline.dataset_id,
            DataQualityRule.is_active == True,  # noqa: E712
        )
        .count()
    )
    return _build_validation_result(pipeline, _pipeline_diagnostics(pipeline, active_rule_count))


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
    _remove_pipeline_schedule(pipeline_id)
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
    if payload.window_start and payload.window_end and payload.window_start > payload.window_end:
        raise HTTPException(status_code=400, detail="补数窗口开始时间不能晚于结束时间")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    active_rule_count = (
        db.query(DataQualityRule)
        .filter(
            DataQualityRule.pipeline_id == pipeline.id,
            DataQualityRule.dataset_id == pipeline.dataset_id,
            DataQualityRule.is_active == True,  # noqa: E712
        )
        .count()
    )
    validation = _build_validation_result(pipeline, _pipeline_diagnostics(pipeline, active_rule_count))
    if validation.critical_count:
        first_critical = next(item for item in validation.diagnostics if item.severity == "critical")
        raise HTTPException(status_code=400, detail=f"管道上线检查未通过：{first_critical.message}")
    now = datetime.now(timezone.utc)
    dataset = _get_dataset_for_user(db, pipeline.dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    active_rules = (
        db.query(DataQualityRule)
        .filter(
            DataQualityRule.pipeline_id == pipeline.id,
            DataQualityRule.dataset_id == pipeline.dataset_id,
            DataQualityRule.is_active == True,  # noqa: E712
        )
        .order_by(DataQualityRule.id.asc())
        .all()
    )
    try:
        execution = execute_pipeline_dag(
            pipeline,
            dataset,
            datasource,
            payload,
            extractor=_execute_dataset_extract,
            dataset_resolver=_build_dataset_resolver(db, current_user),
            datasource_resolver=_build_datasource_resolver(db, current_user),
            quality_rules=active_rules,
            quality_evaluator=_evaluate_quality_rules,
            now=now,
            persist_load=not payload.dry_run,
        )
        node_logs = execution.node_logs
        records_read = execution.records_read
        records_written = execution.records_written
        records_failed = execution.records_failed
        run_status = execution.status
        error_message = execution.error_message
    except Exception as exc:
        node_logs = {
            "summary": {
                "node_count": len((pipeline.dag_json or {}).get("nodes", []) or []),
                "edge_count": len((pipeline.dag_json or {}).get("edges", []) or []),
                "quality": "not_checked",
                "error": str(exc),
                "run_window": {
                    "start": payload.window_start.isoformat() if payload.window_start else None,
                    "end": payload.window_end.isoformat() if payload.window_end else None,
                },
            },
            "nodes": [],
        }
        records_read = 0
        records_written = 0
        records_failed = 0
        run_status = "failed"
        error_message = f"管道执行失败: {exc}"

    duration_ms = int((datetime.now(timezone.utc) - now).total_seconds() * 1000)
    run = DataPipelineRun(
        pipeline_id=pipeline.id,
        mode=payload.mode,
        status=run_status,
        reason=payload.reason,
        node_logs_json=node_logs,
        records_read=records_read,
        records_written=records_written,
        records_failed=records_failed,
        error_message=error_message,
        duration_ms=duration_ms,
        org_id=pipeline.org_id,
        triggered_by_id=getattr(current_user, "id", None),
        finished_at=now,
    )
    pipeline.last_run_status = run_status
    pipeline.last_run_at = now
    pipeline.status = "active" if run_status == "success" and pipeline.status == "draft" else pipeline.status
    if not payload.dry_run:
        dataset.last_refresh_status = "success" if run_status == "success" else "error"
        dataset.last_refresh_at = now
        dataset.last_refresh_row_count = records_written if run_status == "success" else records_read
        db.add(
            DatasetRefreshLog(
                dataset_id=dataset.id,
                status=dataset.last_refresh_status,
                row_count=dataset.last_refresh_row_count,
                message="管道运行成功" if run_status == "success" else error_message,
                org_id=dataset.org_id,
                triggered_by_id=getattr(current_user, "id", None),
            )
        )
    db.add(run)
    db.commit()
    db.refresh(run)
    notify_result = _dispatch_pipeline_notifications(db, pipeline, run, current_user)
    if notify_result:
        run.notify_result_json = notify_result
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
        detail={"mode": payload.mode, "run_id": run.id, "status": run.status, "records_read": records_read, "records_written": records_written},
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


@router.post("/pipelines/{pipeline_id}/preview", response_model=PipelinePreviewOut)
def preview_pipeline(
    pipeline_id: int,
    payload: PipelinePreviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    dataset = _get_dataset_for_user(db, pipeline.dataset_id, current_user)
    datasource = _get_datasource_for_user(db, dataset.datasource_id, current_user)
    request = payload or PipelinePreviewRequest()
    limit = max(1, min(int(request.limit or 100), 500))
    node_ids = {
        str(node.get("id"))
        for node in (pipeline.dag_json or {}).get("nodes", []) or []
        if isinstance(node, dict) and node.get("id")
    }
    if request.node_id and request.node_id not in node_ids:
        raise HTTPException(status_code=400, detail=f"预览节点不存在: {request.node_id}")
    active_rules = (
        db.query(DataQualityRule)
        .filter(
            DataQualityRule.pipeline_id == pipeline.id,
            DataQualityRule.dataset_id == pipeline.dataset_id,
            DataQualityRule.is_active == True,  # noqa: E712
        )
        .order_by(DataQualityRule.id.asc())
        .all()
    )
    execution = execute_pipeline_dag(
        pipeline,
        dataset,
        datasource,
        PipelineRunRequest(mode="manual", reason="preview", dry_run=True),
        extractor=_execute_dataset_extract,
        dataset_resolver=_build_dataset_resolver(db, current_user),
        datasource_resolver=_build_datasource_resolver(db, current_user),
        quality_rules=active_rules,
        quality_evaluator=_evaluate_quality_rules,
        now=datetime.now(timezone.utc),
        until_node_id=request.node_id,
        limit=limit,
        persist_load=False,
    )
    return PipelinePreviewOut(
        pipeline_id=pipeline.id,
        node_id=request.node_id,
        columns=execution.columns,
        rows=execution.rows[:limit],
        row_count=execution.node_logs.get("summary", {}).get("final_row_count", len(execution.rows)),
        node_logs_json=execution.node_logs,
    )


@router.get("/pipelines/{pipeline_id}/lineage", response_model=PipelineLineageOut)
def get_pipeline_lineage(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    dataset = _get_dataset_for_user(db, pipeline.dataset_id, current_user)
    fields_json = dataset.fields_json if isinstance(dataset.fields_json, dict) else {}
    dag = pipeline.dag_json or {}
    nodes = [
        {
            "id": str(node.get("id")),
            "label": node.get("label") or node.get("id"),
            "type": node.get("type") or "task",
            "config_keys": sorted((node.get("config") or {}).keys()) if isinstance(node.get("config"), dict) else [],
        }
        for node in dag.get("nodes", []) or []
        if isinstance(node, dict) and node.get("id")
    ]
    target_tables = [
        (node.get("config") or {}).get("target_table")
        for node in dag.get("nodes", []) or []
        if isinstance(node, dict) and node.get("type") in {"load", "sink"} and isinstance(node.get("config"), dict)
    ]
    sources: list[dict[str, Any]] = []
    for node in dag.get("nodes", []) or []:
        if not isinstance(node, dict) or node.get("type") not in SOURCE_NODE_TYPES:
            continue
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        source_dataset = dataset
        if config.get("dataset_id"):
            source_dataset = _get_dataset_for_user(db, int(config["dataset_id"]), current_user)
        source_fields_json = source_dataset.fields_json if isinstance(source_dataset.fields_json, dict) else {}
        sources.append(
            {
                "node_id": str(node.get("id")),
                "type": node.get("type"),
                "dataset_id": source_dataset.id,
                "dataset_name": source_dataset.name,
                "datasource_id": int(config.get("datasource_id") or source_dataset.datasource_id),
                "table": source_fields_json.get("table"),
                "fields": source_fields_json.get("fields") or source_fields_json.get("dimensions") or [],
            }
        )
    return PipelineLineageOut(
        pipeline_id=pipeline.id,
        source={
            "datasource_id": dataset.datasource_id,
            "table": fields_json.get("table"),
            "fields": fields_json.get("fields") or fields_json.get("dimensions") or [],
            "sources": sources,
        },
        target={
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "target_tables": [table for table in target_tables if table],
        },
        nodes=nodes,
        edges=[
            {"source": edge.get("source"), "target": edge.get("target")}
            for edge in dag.get("edges", []) or []
            if isinstance(edge, dict) and edge.get("source") and edge.get("target")
        ],
    )


@router.get("/pipelines/{pipeline_id}/versions", response_model=list[PipelineVersionOut])
def list_pipeline_versions(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.read")
    _get_pipeline_for_user(db, pipeline_id, current_user)
    return (
        db.query(DataPipelineVersion)
        .filter(DataPipelineVersion.pipeline_id == pipeline_id)
        .order_by(DataPipelineVersion.version.desc())
        .all()
    )


@router.post("/pipelines/{pipeline_id}/versions/publish", response_model=PipelineVersionOut)
def publish_pipeline_version(
    pipeline_id: int,
    comment: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_action(current_user, "pipeline.update")
    pipeline = _get_pipeline_for_user(db, pipeline_id, current_user)
    _validate_dag(pipeline.dag_json or {})
    latest = (
        db.query(DataPipelineVersion)
        .filter(DataPipelineVersion.pipeline_id == pipeline.id)
        .order_by(DataPipelineVersion.version.desc())
        .first()
    )
    next_version = int(latest.version if latest else 0) + 1
    version = DataPipelineVersion(
        pipeline_id=pipeline.id,
        version=next_version,
        status="published",
        dag_json=pipeline.dag_json,
        config_json={
            "run_mode": pipeline.run_mode,
            "schedule_cron": pipeline.schedule_cron,
            "environment": pipeline.environment,
            "priority": pipeline.priority,
            "sla_minutes": pipeline.sla_minutes,
            "retry_count": pipeline.retry_count,
            "timeout_minutes": pipeline.timeout_minutes,
            "alert_policy_json": pipeline.alert_policy_json,
            "state_json": pipeline.state_json,
        },
        comment=comment,
        org_id=pipeline.org_id,
        created_by=getattr(current_user, "id", None),
    )
    pipeline.current_version = next_version
    pipeline.published_version = next_version
    pipeline.status = "active" if pipeline.status == "draft" else pipeline.status
    db.add(version)
    db.commit()
    db.refresh(version)
    _sync_pipeline_schedule(pipeline.id)
    try_record_audit_log(
        db,
        actor=current_user,
        action="pipeline.publish",
        resource_type="data_pipeline",
        resource_id=pipeline.id,
        resource_name=pipeline.name,
        org_id=pipeline.org_id,
        message="数据集成管道版本已发布",
        detail={"version": next_version},
    )
    return version


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
