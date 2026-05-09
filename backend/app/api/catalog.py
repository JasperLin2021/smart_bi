from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import cast, or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.catalog import (
    AssetLineage,
    AssetNotification,
    AssetSubscription,
    CatalogCategory,
    DataAsset,
)
from app.models.dashboard_config import Dashboard
from app.models.big_screen import BigScreen
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.integration import ExternalIdentity, IntegrationConfig
from app.models.user import User
from app.schemas.catalog import (
    AssetFieldsResponse,
    AssetLineageResponse,
    AssetNotificationOut,
    AssetPreviewResponse,
    AssetReferencesResponse,
    AssetReferenceItem,
    CatalogCategoryCreate,
    CatalogCategoryOut,
    CatalogCategoryTree,
    CatalogCategoryUpdate,
    DataAssetCategoryUpdate,
    DataAssetCreate,
    DataAssetListResponse,
    DataAssetOut,
    DataAssetStatusUpdate,
    DataAssetUpdate,
    FieldInfo,
    LineageCreate,
    LineageEdge,
    LineageNode,
    LineageOut,
    NotificationListResponse,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

VALID_ASSET_STATUSES = {"draft", "published", "archived"}
VALID_ASSET_TYPE_ORDER = ("metric", "dataset", "table", "dashboard", "big_screen")
VALID_ASSET_TYPES = set(VALID_ASSET_TYPE_ORDER)
ASSET_TYPE_LABELS = {
    "metric": "指标",
    "dataset": "数据集",
    "table": "数据表",
    "dashboard": "看板",
    "big_screen": "大屏",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _ensure_status(status: str) -> None:
    if status not in VALID_ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="无效资产状态")


def _asset_type_choices_text() -> str:
    return "、".join(
        f"{ASSET_TYPE_LABELS[asset_type]}({asset_type})"
        for asset_type in VALID_ASSET_TYPE_ORDER
    )


def _ensure_asset_type(asset_type: str) -> None:
    if asset_type not in VALID_ASSET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效资产类型 {asset_type}，仅支持：{_asset_type_choices_text()}",
        )


def _supported_asset_query(db: Session):
    return db.query(DataAsset).filter(DataAsset.asset_type.in_(VALID_ASSET_TYPE_ORDER))


def _can_manage_asset(user: User, asset: DataAsset) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and asset.org_id == user.org_id:
        return True
    return asset.owner_id == user.id


def _apply_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(DataAsset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(DataAsset.status == "published", DataAsset.owner_id == user.id))


def _build_category_tree(categories: list[CatalogCategory]) -> list[CatalogCategoryTree]:
    by_id: dict[int, CatalogCategoryTree] = {
        c.id: CatalogCategoryTree.model_validate(c) for c in categories
    }
    roots: list[CatalogCategoryTree] = []
    for node in by_id.values():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def _notify_subscribers(db: Session, asset_id: int, message: str) -> None:
    """Create in-app notifications for all subscribers and push via WeChat Work if configured."""
    from sqlalchemy import inspect as sa_inspect
    bind = db.get_bind()
    if bind is not None and not sa_inspect(bind).has_table(AssetSubscription.__tablename__):
        return
    subs = db.query(AssetSubscription).filter(AssetSubscription.asset_id == asset_id).all()
    if not subs:
        return

    user_ids = [s.user_id for s in subs]
    for uid in user_ids:
        db.add(AssetNotification(user_id=uid, asset_id=asset_id, message=message))

    db.flush()

    # WeChat Work push
    try:
        _push_wechat_work(db, user_ids, message)
    except Exception as exc:
        logger.warning("企微通知推送失败: %s", exc)


def _push_wechat_work(db: Session, user_ids: list[int], message: str) -> None:
    from app.core.wechat_work import WECHAT_WORK_PROVIDER, WechatWorkClient

    cfg = (
        db.query(IntegrationConfig)
        .filter(
            IntegrationConfig.provider == WECHAT_WORK_PROVIDER,
            IntegrationConfig.enabled.is_(True),
        )
        .first()
    )
    if not cfg or not cfg.corp_id or not cfg.app_secret or not cfg.agent_id:
        return

    client = WechatWorkClient(
        corp_id=cfg.corp_id,
        agent_id=cfg.agent_id,
        app_secret=cfg.app_secret,
        callback_url=cfg.callback_url or "",
    )
    access_token = client.get_access_token()

    identities = (
        db.query(ExternalIdentity)
        .filter(
            ExternalIdentity.user_id.in_(user_ids),
            ExternalIdentity.provider == WECHAT_WORK_PROVIDER,
        )
        .all()
    )
    for identity in identities:
        try:
            client.send_textcard(
                access_token=access_token,
                to_user=identity.external_user_id,
                title="数据资产变更通知",
                content=message,
            )
        except Exception as exc:
            logger.warning("企微推送用户 %s 失败: %s", identity.external_user_id, exc)


# ── categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CatalogCategoryTree])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_filter = None if current_user.role == "super_admin" else current_user.org_id
    q = db.query(CatalogCategory)
    if org_filter is not None:
        q = q.filter(CatalogCategory.org_id == org_filter)
    return _build_category_tree(
        q.order_by(CatalogCategory.sort_order, CatalogCategory.id).all()
    )


@router.put("/categories/reorder")
def reorder_categories(
    payload: list,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.schemas.catalog import CategoryReorderItem
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    items = [CategoryReorderItem.model_validate(i) for i in payload]
    for item in items:
        db.query(CatalogCategory).filter(CatalogCategory.id == item.id).update(
            {"sort_order": item.sort_order}
        )
    db.commit()
    return {"ok": True}


@router.post("/categories", response_model=CatalogCategoryOut)
def create_category(
    payload: CatalogCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    org_id = payload.org_id if current_user.role == "super_admin" else current_user.org_id
    cat = CatalogCategory(name=payload.name, parent_id=payload.parent_id, org_id=org_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=CatalogCategoryOut)
def update_category(
    category_id: int,
    payload: CatalogCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    cat = db.query(CatalogCategory).filter(CatalogCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    cat = db.query(CatalogCategory).filter(CatalogCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    # Cascade: set asset category_id to NULL (FK ondelete=SET NULL handles it in DB)
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ── assets ────────────────────────────────────────────────────────────────────

@router.get("/assets", response_model=DataAssetListResponse)
def list_assets(
    q: str | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    category_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type:
        _ensure_asset_type(asset_type)
    query = _apply_visibility(_supported_asset_query(db), current_user)
    if q:
        query = query.filter(DataAsset.name.ilike(f"%{q}%"))
    if asset_type:
        query = query.filter(DataAsset.asset_type == asset_type)
    if status:
        query = query.filter(DataAsset.status == status)
    if category_id is not None:
        query = query.filter(DataAsset.category_id == category_id)
    return {"items": query.order_by(DataAsset.id.desc()).all()}


@router.post("/assets", response_model=DataAssetOut)
def create_asset(
    payload: DataAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    _ensure_asset_type(payload.asset_type)
    _ensure_status(payload.status)
    org_id = payload.org_id if current_user.role == "super_admin" else current_user.org_id
    asset = DataAsset(
        **payload.model_dump(exclude={"org_id", "owner_id"}),
        org_id=org_id,
        owner_id=payload.owner_id or current_user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/assets/{asset_id}", response_model=DataAssetOut)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    # Increment view count atomically
    db.execute(
        text("UPDATE data_assets SET view_count = view_count + 1 WHERE id = :id"),
        {"id": asset_id},
    )
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/assets/{asset_id}", response_model=DataAssetOut)
def update_asset(
    asset_id: int,
    payload: DataAssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _supported_asset_query(db).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    if not _can_manage_asset(current_user, asset):
        raise HTTPException(status_code=403, detail="无权限")
    values = payload.model_dump(exclude_unset=True)
    if "status" in values:
        _ensure_status(values["status"])
    for key, value in values.items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/assets/{asset_id}/status", response_model=DataAssetOut)
def update_asset_status(
    asset_id: int,
    payload: DataAssetStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_status(payload.status)
    asset = _supported_asset_query(db).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    if not _can_manage_asset(current_user, asset):
        raise HTTPException(status_code=403, detail="无权限")
    old_status = asset.status
    asset.status = payload.status
    db.commit()
    db.refresh(asset)
    if old_status != payload.status:
        _notify_subscribers(
            db,
            asset_id,
            f"资产「{asset.name}」状态已变更：{old_status} → {payload.status}",
        )
        db.commit()
    return asset


@router.put("/assets/{asset_id}/category", response_model=DataAssetOut)
def update_asset_category(
    asset_id: int,
    payload: DataAssetCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _supported_asset_query(db).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    if not _can_manage_asset(current_user, asset):
        raise HTTPException(status_code=403, detail="无权限")
    asset.category_id = payload.category_id
    db.commit()
    db.refresh(asset)
    return asset


# ── fields ────────────────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/fields", response_model=AssetFieldsResponse)
def get_asset_fields(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")

    if asset.asset_type == "dataset":
        fields_raw = (asset.metadata_json or {}).get("fields") or {}
        raw_list = fields_raw.get("fields", []) if isinstance(fields_raw, dict) else []
        columns = [
            FieldInfo(
                name=f.get("name", f) if isinstance(f, dict) else str(f),
                type=f.get("type", "unknown") if isinstance(f, dict) else "unknown",
                description=f.get("description") if isinstance(f, dict) else None,
            )
            for f in raw_list
        ]
        return AssetFieldsResponse(columns=columns)

    if asset.asset_type == "table" and asset.datasource_id:
        ds = db.query(DataSource).filter(DataSource.id == asset.datasource_id).first()
        if not ds:
            return AssetFieldsResponse(columns=[])
        schema_raw = ds.schema_metadata
        if schema_raw:
            try:
                schema = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
                table_name = asset.name
                for t in schema.get("tables", []):
                    if t.get("name") == table_name:
                        columns = [
                            FieldInfo(
                                name=c.get("name", ""),
                                type=c.get("type", "unknown"),
                                description=c.get("description"),
                            )
                            for c in t.get("columns", [])
                        ]
                        return AssetFieldsResponse(columns=columns)
            except (json.JSONDecodeError, TypeError):
                pass
        return AssetFieldsResponse(columns=[])

    return AssetFieldsResponse(columns=[])


# ── preview ───────────────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/preview", response_model=AssetPreviewResponse)
def preview_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")

    if asset.asset_type not in ("dataset", "table"):
        raise HTTPException(status_code=400, detail="该资产类型不支持数据预览")

    if asset.asset_type == "dataset" and asset.asset_id:
        from app.api.datasets import _execute_dataset_preview
        dataset = db.query(Dataset).filter(Dataset.id == asset.asset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="数据集不存在")
        ds = db.query(DataSource).filter(DataSource.id == dataset.datasource_id).first()
        if not ds:
            raise HTTPException(status_code=404, detail="数据源不存在")
        try:
            result = _execute_dataset_preview(dataset, ds, limit=20)
            return AssetPreviewResponse(columns=result.get("columns", []), rows=result.get("rows", []))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"预览失败: {exc}")

    if asset.asset_type == "table" and asset.datasource_id:
        from app.api.datasource import _fetch_database_preview, _fetch_excel_preview
        ds = db.query(DataSource).filter(DataSource.id == asset.datasource_id).first()
        if not ds:
            raise HTTPException(status_code=404, detail="数据源不存在")
        try:
            if ds.source_type == "excel":
                result = _fetch_excel_preview(ds.database_url, asset.name, 20)
            else:
                result = _fetch_database_preview(ds.database_url, asset.name, 20)
            return AssetPreviewResponse(columns=result.get("columns", []), rows=result.get("rows", []))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"预览失败: {exc}")

    raise HTTPException(status_code=400, detail="无法预览此资产")


# ── references ────────────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/references", response_model=AssetReferencesResponse)
def get_asset_references(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")

    refs: list[AssetReferenceItem] = []
    search_val = str(asset.asset_id or asset_id)

    org_filter = current_user.org_id if current_user.role != "super_admin" else None

    # Check dashboards
    dash_q = db.query(Dashboard)
    if org_filter:
        dash_q = dash_q.filter(Dashboard.org_id == org_filter)
    for dash in dash_q.all():
        config_str = json.dumps(dash.layout_json or {})
        if search_val in config_str:
            refs.append(AssetReferenceItem(type="dashboard", name=dash.title, id=dash.id))

    # Check big screens
    screen_q = db.query(BigScreen)
    if org_filter:
        screen_q = screen_q.filter(BigScreen.org_id == org_filter)
    for screen in screen_q.all():
        config_str = json.dumps(screen.data_bindings_json or {})
        if search_val in config_str:
            refs.append(AssetReferenceItem(type="big_screen", name=screen.title, id=screen.id))

    return AssetReferencesResponse(count=len(refs), references=refs)


# ── lineage ───────────────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/lineage", response_model=AssetLineageResponse)
def get_asset_lineage(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")

    # Collect edges within 2 hops
    edges_raw: list[AssetLineage] = []
    visited_ids: set[int] = {asset_id}
    frontier = {asset_id}

    for _ in range(2):
        if not frontier:
            break
        new_edges = (
            db.query(AssetLineage)
            .filter(
                AssetLineage.source_id.in_(frontier) | AssetLineage.target_id.in_(frontier)
            )
            .all()
        )
        next_frontier: set[int] = set()
        for e in new_edges:
            if e not in edges_raw:
                edges_raw.append(e)
            for nid in (e.source_id, e.target_id):
                if nid not in visited_ids:
                    visited_ids.add(nid)
                    next_frontier.add(nid)
        frontier = next_frontier

    # Collect all node IDs
    node_ids = visited_ids
    assets = _supported_asset_query(db).filter(DataAsset.id.in_(node_ids)).all()
    valid_node_ids = {a.id for a in assets}
    nodes = [LineageNode(id=a.id, name=a.name, asset_type=a.asset_type) for a in assets]
    edges = [
        LineageEdge(source=e.source_id, target=e.target_id, rel_type=e.rel_type)
        for e in edges_raw
        if e.source_id in valid_node_ids and e.target_id in valid_node_ids
    ]

    return AssetLineageResponse(nodes=nodes, edges=edges)


@router.post("/lineage", response_model=LineageOut)
def create_lineage(
    payload: LineageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    asset_ids = {payload.source_id, payload.target_id}
    supported_count = (
        _supported_asset_query(db)
        .filter(DataAsset.id.in_(asset_ids))
        .count()
    )
    if supported_count != len(asset_ids):
        raise HTTPException(status_code=404, detail="数据资产不存在")
    existing = (
        db.query(AssetLineage)
        .filter(AssetLineage.source_id == payload.source_id, AssetLineage.target_id == payload.target_id)
        .first()
    )
    if existing:
        return existing
    org_id = payload.org_id if current_user.role == "super_admin" else current_user.org_id
    lineage = AssetLineage(
        source_id=payload.source_id,
        target_id=payload.target_id,
        rel_type=payload.rel_type,
        org_id=org_id,
    )
    db.add(lineage)
    db.commit()
    db.refresh(lineage)
    return lineage


@router.delete("/lineage/{lineage_id}")
def delete_lineage(
    lineage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")
    lin = db.query(AssetLineage).filter(AssetLineage.id == lineage_id).first()
    if not lin:
        raise HTTPException(status_code=404, detail="血缘记录不存在")
    db.delete(lin)
    db.commit()
    return {"ok": True}


# ── subscriptions ─────────────────────────────────────────────────────────────

@router.get("/assets/{asset_id}/subscription", response_model=SubscriptionStatus)
def get_subscription_status(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    sub = (
        db.query(AssetSubscription)
        .filter(AssetSubscription.user_id == current_user.id, AssetSubscription.asset_id == asset_id)
        .first()
    )
    return SubscriptionStatus(subscribed=sub is not None)


@router.post("/assets/{asset_id}/subscribe", response_model=SubscriptionStatus)
def subscribe_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = _apply_visibility(_supported_asset_query(db), current_user).filter(DataAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="数据资产不存在")
    existing = (
        db.query(AssetSubscription)
        .filter(AssetSubscription.user_id == current_user.id, AssetSubscription.asset_id == asset_id)
        .first()
    )
    if not existing:
        db.add(AssetSubscription(user_id=current_user.id, asset_id=asset_id))
        db.commit()
    return SubscriptionStatus(subscribed=True)


@router.delete("/assets/{asset_id}/subscribe", response_model=SubscriptionStatus)
def unsubscribe_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(AssetSubscription)
        .filter(AssetSubscription.user_id == current_user.id, AssetSubscription.asset_id == asset_id)
        .first()
    )
    if sub:
        db.delete(sub)
        db.commit()
    return SubscriptionStatus(subscribed=False)


# ── notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    unread: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(AssetNotification).filter(AssetNotification.user_id == current_user.id)
    if unread is True:
        q = q.filter(AssetNotification.is_read.is_(False))
    items = q.order_by(AssetNotification.id.desc()).limit(50).all()
    unread_count = (
        db.query(AssetNotification)
        .filter(AssetNotification.user_id == current_user.id, AssetNotification.is_read.is_(False))
        .count()
    )
    return NotificationListResponse(items=items, unread_count=unread_count)


@router.put("/notifications/{notification_id}/read", response_model=AssetNotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = (
        db.query(AssetNotification)
        .filter(AssetNotification.id == notification_id, AssetNotification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="通知不存在")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.put("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(AssetNotification).filter(
        AssetNotification.user_id == current_user.id,
        AssetNotification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}
