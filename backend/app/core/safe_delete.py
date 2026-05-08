from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect, or_
from sqlalchemy.orm import Session

from app.models.access_request import AccessRequest
from app.models.action_item import ActionItem
from app.models.alert import Alert
from app.models.big_screen import BigScreen
from app.models.catalog import AssetLineage, AssetNotification, AssetSubscription, DataAsset
from app.models.dashboard_config import Dashboard
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.embed_token import EmbedToken
from app.models.integration import ExternalIdentity, ExternalOrgBinding, ExternalPermissionMapping
from app.models.metric import Metric
from app.models.pinned_chart import PinnedChart
from app.models.scheduled_report import ScheduledReport
from app.models.user import User


@dataclass(frozen=True)
class DeleteReference:
    label: str
    count: int
    examples: tuple[str, ...] = ()


def _table_exists(db: Session, model: type) -> bool:
    bind = db.get_bind()
    if bind is None:
        return True
    try:
        return inspect(db.connection()).has_table(model.__tablename__)
    except Exception:
        return True


def _display_name(item: Any, preferred_attr: str | None = None) -> str:
    attrs = [preferred_attr] if preferred_attr else []
    attrs.extend(["name", "title", "label", "username", "resource_name", "slug", "token"])
    for attr in attrs:
        if not attr:
            continue
        value = getattr(item, attr, None)
        if value:
            return str(value)
    item_id = getattr(item, "id", None)
    return f"#{item_id}" if item_id is not None else str(item)


def _model_ref(
    db: Session,
    label: str,
    model: type,
    *conditions: Any,
    name_attr: str | None = None,
) -> DeleteReference | None:
    if not _table_exists(db, model):
        return None
    query = db.query(model).filter(*conditions)
    count = query.count()
    if count <= 0:
        return None
    examples = tuple(_display_name(item, name_attr) for item in query.limit(3).all())
    return DeleteReference(label=label, count=count, examples=examples)


def _json_has_key_value(value: Any, key: str, target: int) -> bool:
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            if item_key == key:
                try:
                    if int(item_value) == target:
                        return True
                except (TypeError, ValueError):
                    pass
            if _json_has_key_value(item_value, key, target):
                return True
    if isinstance(value, list):
        return any(_json_has_key_value(item, key, target) for item in value)
    return False


def _json_has_value(value: Any, target: int) -> bool:
    try:
        if int(value) == target:
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, dict):
        return any(_json_has_value(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_json_has_value(item, target) for item in value)
    return False


def _json_ref(
    db: Session,
    label: str,
    model: type,
    json_attr: str,
    key: str,
    target: int,
    *conditions: Any,
    name_attr: str | None = None,
) -> DeleteReference | None:
    if not _table_exists(db, model):
        return None
    query = db.query(model)
    if conditions:
        query = query.filter(*conditions)
    matches = [
        item
        for item in query.all()
        if _json_has_key_value(getattr(item, json_attr, None), key, target)
    ]
    if not matches:
        return None
    examples = tuple(_display_name(item, name_attr) for item in matches[:3])
    return DeleteReference(label=label, count=len(matches), examples=examples)


def _json_value_ref(
    db: Session,
    label: str,
    model: type,
    json_attr: str,
    target: int,
    *conditions: Any,
    name_attr: str | None = None,
) -> DeleteReference | None:
    if not _table_exists(db, model):
        return None
    query = db.query(model)
    if conditions:
        query = query.filter(*conditions)
    matches = [
        item
        for item in query.all()
        if _json_has_value(getattr(item, json_attr, None), target)
    ]
    if not matches:
        return None
    examples = tuple(_display_name(item, name_attr) for item in matches[:3])
    return DeleteReference(label=label, count=len(matches), examples=examples)


def _raise_if_referenced(resource_label: str, resource_name: str, refs: list[DeleteReference | None]) -> None:
    blocking_refs = [ref for ref in refs if ref and ref.count > 0]
    if not blocking_refs:
        return

    parts: list[str] = []
    for ref in blocking_refs:
        example_text = f"（如：{'、'.join(ref.examples)}）" if ref.examples else ""
        parts.append(f"{ref.count} 个{ref.label}{example_text}")
    raise HTTPException(
        status_code=409,
        detail=f"无法删除{resource_label}「{resource_name}」，仍被{'; '.join(parts)}引用。请先删除或解绑这些引用。",
    )


def assert_datasource_can_delete(db: Session, datasource: DataSource) -> None:
    refs = [
        _model_ref(db, "数据集", Dataset, Dataset.datasource_id == datasource.id),
        _model_ref(db, "指标", Metric, Metric.datasource_id == datasource.id),
        _model_ref(db, "预警", Alert, Alert.datasource_id == datasource.id),
        _model_ref(db, "定时报告", ScheduledReport, ScheduledReport.datasource_id == datasource.id),
        _model_ref(db, "固定图表", PinnedChart, PinnedChart.datasource_id == datasource.id),
        _model_ref(
            db,
            "待处理访问申请",
            AccessRequest,
            AccessRequest.resource_type == "datasource",
            AccessRequest.resource_id == datasource.id,
            AccessRequest.status == "pending",
            name_attr="resource_name",
        ),
    ]
    _raise_if_referenced("数据源", datasource.name, refs)


def assert_dataset_can_delete(db: Session, dataset: Dataset) -> None:
    refs = [
        _model_ref(db, "指标", Metric, Metric.dataset_id == dataset.id),
        _model_ref(db, "行动项", ActionItem, ActionItem.linked_dataset_id == dataset.id, name_attr="title"),
        _model_ref(
            db,
            "待处理访问申请",
            AccessRequest,
            AccessRequest.resource_type == "dataset",
            AccessRequest.resource_id == dataset.id,
            AccessRequest.status == "pending",
            name_attr="resource_name",
        ),
        _json_ref(db, "看板", Dashboard, "layout_json", "dataset_id", dataset.id, name_attr="title"),
        _json_ref(db, "大屏", BigScreen, "data_bindings_json", "dataset_id", dataset.id, name_attr="title"),
    ]
    _raise_if_referenced("数据集", dataset.name, refs)


def assert_metric_can_delete(db: Session, metric: Metric) -> None:
    refs = [
        _model_ref(db, "预警", Alert, Alert.metric_id == metric.id),
        _model_ref(db, "行动项", ActionItem, ActionItem.linked_metric_id == metric.id, name_attr="title"),
        _json_ref(db, "看板", Dashboard, "layout_json", "metric_id", metric.id, name_attr="title"),
        _json_ref(db, "大屏", BigScreen, "data_bindings_json", "metric_id", metric.id, name_attr="title"),
    ]
    _raise_if_referenced("指标", metric.name, refs)


def assert_dashboard_can_delete(db: Session, dashboard: Dashboard) -> None:
    refs = [
        _model_ref(db, "行动项", ActionItem, ActionItem.linked_dashboard_id == dashboard.id, name_attr="title"),
        _model_ref(
            db,
            "嵌入令牌",
            EmbedToken,
            EmbedToken.resource_type == "dashboard",
            EmbedToken.resource_id == dashboard.id,
            name_attr="label",
        ),
    ]
    _raise_if_referenced("看板", dashboard.title, refs)


def assert_pinned_chart_can_delete(db: Session, chart: PinnedChart) -> None:
    refs = [
        _json_ref(db, "看板", Dashboard, "layout_json", "pinned_chart_id", chart.id, name_attr="title"),
        _model_ref(
            db,
            "嵌入令牌",
            EmbedToken,
            EmbedToken.resource_type == "chart",
            EmbedToken.resource_id == chart.id,
            name_attr="label",
        ),
    ]
    _raise_if_referenced("固定图表", chart.title, refs)


def assert_alert_can_delete(db: Session, alert: Alert) -> None:
    refs = [
        _model_ref(
            db,
            "行动项",
            ActionItem,
            ActionItem.source_type == "alert",
            ActionItem.source_id == str(alert.id),
            name_attr="title",
        )
    ]
    _raise_if_referenced("预警", alert.name, refs)


def assert_user_can_delete(db: Session, user: User) -> None:
    refs = [
        _model_ref(db, "数据集", Dataset, Dataset.owner_id == user.id),
        _model_ref(db, "看板", Dashboard, Dashboard.owner_id == user.id, name_attr="title"),
        _model_ref(db, "大屏", BigScreen, BigScreen.owner_id == user.id, name_attr="title"),
        _model_ref(db, "固定图表", PinnedChart, PinnedChart.user_id == user.id, name_attr="title"),
        _model_ref(db, "预警", Alert, Alert.created_by == user.id),
        _model_ref(db, "定时报告", ScheduledReport, ScheduledReport.created_by == user.id),
        _model_ref(
            db,
            "行动项",
            ActionItem,
            or_(ActionItem.owner_id == user.id, ActionItem.created_by == user.id),
            name_attr="title",
        ),
        _model_ref(db, "外部身份绑定", ExternalIdentity, ExternalIdentity.user_id == user.id, name_attr="display_name"),
        _model_ref(
            db,
            "待处理访问申请",
            AccessRequest,
            AccessRequest.requester_id == user.id,
            AccessRequest.status == "pending",
            name_attr="resource_name",
        ),
        _json_value_ref(db, "共享看板", Dashboard, "shared_user_ids", user.id, name_attr="title"),
    ]
    _raise_if_referenced("用户", user.username, refs)


def assert_organization_can_delete(db: Session, org: Any) -> None:
    refs = [
        _model_ref(db, "用户", User, User.org_id == org.id, name_attr="username"),
        _model_ref(db, "数据源", DataSource, DataSource.org_id == org.id),
        _model_ref(db, "数据集", Dataset, Dataset.org_id == org.id),
        _model_ref(db, "看板", Dashboard, Dashboard.org_id == org.id, name_attr="title"),
        _model_ref(db, "大屏", BigScreen, BigScreen.org_id == org.id, name_attr="title"),
        _model_ref(db, "行动项", ActionItem, ActionItem.org_id == org.id, name_attr="title"),
        _model_ref(db, "数据目录资产", DataAsset, DataAsset.org_id == org.id),
        _model_ref(db, "外部组织绑定", ExternalOrgBinding, ExternalOrgBinding.org_id == org.id),
        _model_ref(db, "外部权限映射", ExternalPermissionMapping, ExternalPermissionMapping.org_id == org.id),
        _model_ref(
            db,
            "待处理访问申请",
            AccessRequest,
            AccessRequest.org_id == org.id,
            AccessRequest.status == "pending",
            name_attr="resource_name",
        ),
    ]
    _raise_if_referenced("企业", org.name, refs)


def delete_catalog_asset(db: Session, asset_type: str, asset_id: int) -> None:
    if not _table_exists(db, DataAsset):
        return
    assets = (
        db.query(DataAsset)
        .filter(DataAsset.asset_type == asset_type, DataAsset.asset_id == asset_id)
        .all()
    )
    for asset in assets:
        if _table_exists(db, AssetLineage):
            db.query(AssetLineage).filter(
                (AssetLineage.source_id == asset.id) | (AssetLineage.target_id == asset.id)
            ).delete(synchronize_session=False)
        if _table_exists(db, AssetSubscription):
            db.query(AssetSubscription).filter(AssetSubscription.asset_id == asset.id).delete(synchronize_session=False)
        if _table_exists(db, AssetNotification):
            db.query(AssetNotification).filter(AssetNotification.asset_id == asset.id).delete(synchronize_session=False)
        db.delete(asset)
