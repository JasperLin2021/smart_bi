import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.message_dispatcher import MessageEvent, dispatch_message_event
from app.core.permissions import require_super_admin
from app.db.session import get_db
from app.models.integration import (
    ExternalOrgBinding,
    ExternalPermissionMapping,
    IntegrationConfig,
    MessageDelivery,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.integration import (
    ExternalOrgBindingCreate,
    ExternalOrgBindingOut,
    ExternalPermissionMappingCreate,
    ExternalPermissionMappingOut,
    ExternalPermissionMappingUpdate,
    MessageDeliveryOut,
    WechatWorkConfigOut,
    WechatWorkConfigUpdate,
    WechatWorkMessageTestRequest,
)

router = APIRouter(prefix="/integrations/wechat-work", tags=["integrations"])

WECHAT_WORK_PROVIDER = "wechat_work"
VALID_EXTERNAL_ROLES = {"user", "org_admin"}


def _dump_permissions(value: dict[str, bool] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _parse_permissions(raw_value: str | None) -> dict[str, bool] | None:
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): bool(value) for key, value in parsed.items()}


def _ensure_org(db: Session, org_id: int) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="企业不存在")
    return org


def _validate_external_role(role: str) -> None:
    if role not in VALID_EXTERNAL_ROLES:
        raise HTTPException(status_code=400, detail="企微部门映射仅允许 user 或 org_admin")


def _get_or_create_wechat_config(db: Session) -> IntegrationConfig:
    record = db.query(IntegrationConfig).filter(IntegrationConfig.provider == WECHAT_WORK_PROVIDER).first()
    if record:
        return record
    record = IntegrationConfig(provider=WECHAT_WORK_PROVIDER, name="企业微信", enabled=False)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _config_to_out(record: IntegrationConfig) -> WechatWorkConfigOut:
    return WechatWorkConfigOut(
        id=record.id,
        provider=record.provider,
        name=record.name,
        enabled=bool(record.enabled),
        corp_id=record.corp_id,
        agent_id=record.agent_id,
        callback_url=record.callback_url,
        robot_webhook_url=record.robot_webhook_url,
        app_secret_set=bool(record.app_secret),
    )


def _binding_to_out(binding: ExternalOrgBinding, db: Session) -> ExternalOrgBindingOut:
    org = db.query(Organization).filter(Organization.id == binding.org_id).first()
    return ExternalOrgBindingOut(
        id=binding.id,
        provider=binding.provider,
        external_corp_id=binding.external_corp_id,
        org_id=binding.org_id,
        org_name=org.name if org else None,
    )


def _mapping_to_out(mapping: ExternalPermissionMapping, db: Session) -> ExternalPermissionMappingOut:
    org = db.query(Organization).filter(Organization.id == mapping.org_id).first()
    return ExternalPermissionMappingOut(
        id=mapping.id,
        provider=mapping.provider,
        external_corp_id=mapping.external_corp_id,
        external_department_id=mapping.external_department_id,
        org_id=mapping.org_id,
        org_name=org.name if org else None,
        role=mapping.role,
        data_scope=mapping.data_scope,
        menu_permissions=_parse_permissions(mapping.menu_permissions),
        action_permissions=_parse_permissions(mapping.action_permissions),
        priority=mapping.priority,
        enabled=bool(mapping.enabled),
    )


@router.get("/config", response_model=WechatWorkConfigOut)
def get_wechat_work_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    return _config_to_out(_get_or_create_wechat_config(db))


@router.put("/config", response_model=WechatWorkConfigOut)
def update_wechat_work_config(
    payload: WechatWorkConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    record = _get_or_create_wechat_config(db)
    data = payload.model_dump(exclude_unset=True)
    if data.get("app_secret") is None:
        data.pop("app_secret", None)
    for key, value in data.items():
        setattr(record, key, value)
    if not record.name:
        record.name = "企业微信"
    db.commit()
    db.refresh(record)
    return _config_to_out(record)


@router.get("/org-bindings", response_model=list[ExternalOrgBindingOut])
def list_wechat_work_org_bindings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    bindings = (
        db.query(ExternalOrgBinding)
        .filter(ExternalOrgBinding.provider == WECHAT_WORK_PROVIDER)
        .order_by(ExternalOrgBinding.id.asc())
        .all()
    )
    return [_binding_to_out(binding, db) for binding in bindings]


@router.post("/org-bindings", response_model=ExternalOrgBindingOut, status_code=status.HTTP_201_CREATED)
def create_wechat_work_org_binding(
    payload: ExternalOrgBindingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    _ensure_org(db, payload.org_id)
    existing = (
        db.query(ExternalOrgBinding)
        .filter(
            ExternalOrgBinding.provider == WECHAT_WORK_PROVIDER,
            ExternalOrgBinding.external_corp_id == payload.external_corp_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该 CorpID 已绑定")
    binding = ExternalOrgBinding(
        provider=WECHAT_WORK_PROVIDER,
        external_corp_id=payload.external_corp_id,
        org_id=payload.org_id,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return _binding_to_out(binding, db)


@router.delete("/org-bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wechat_work_org_binding(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    binding = (
        db.query(ExternalOrgBinding)
        .filter(ExternalOrgBinding.id == binding_id, ExternalOrgBinding.provider == WECHAT_WORK_PROVIDER)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    db.delete(binding)
    db.commit()
    return None


@router.get("/permission-mappings", response_model=list[ExternalPermissionMappingOut])
def list_wechat_work_permission_mappings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    mappings = (
        db.query(ExternalPermissionMapping)
        .filter(ExternalPermissionMapping.provider == WECHAT_WORK_PROVIDER)
        .order_by(ExternalPermissionMapping.priority.asc(), ExternalPermissionMapping.id.asc())
        .all()
    )
    return [_mapping_to_out(mapping, db) for mapping in mappings]


@router.post("/permission-mappings", response_model=ExternalPermissionMappingOut, status_code=status.HTTP_201_CREATED)
def create_wechat_work_permission_mapping(
    payload: ExternalPermissionMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    _validate_external_role(payload.role)
    _ensure_org(db, payload.org_id)
    mapping = ExternalPermissionMapping(
        provider=WECHAT_WORK_PROVIDER,
        external_corp_id=payload.external_corp_id,
        external_department_id=payload.external_department_id,
        org_id=payload.org_id,
        role=payload.role,
        data_scope=payload.data_scope,
        menu_permissions=_dump_permissions(payload.menu_permissions),
        action_permissions=_dump_permissions(payload.action_permissions),
        priority=payload.priority,
        enabled=payload.enabled,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _mapping_to_out(mapping, db)


@router.put("/permission-mappings/{mapping_id}", response_model=ExternalPermissionMappingOut)
def update_wechat_work_permission_mapping(
    mapping_id: int,
    payload: ExternalPermissionMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    mapping = (
        db.query(ExternalPermissionMapping)
        .filter(ExternalPermissionMapping.id == mapping_id, ExternalPermissionMapping.provider == WECHAT_WORK_PROVIDER)
        .first()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="权限映射不存在")
    values = payload.model_dump(exclude_unset=True)
    if "role" in values:
        _validate_external_role(values["role"])
    if "org_id" in values:
        _ensure_org(db, values["org_id"])
    if "menu_permissions" in values:
        values["menu_permissions"] = _dump_permissions(values["menu_permissions"])
    if "action_permissions" in values:
        values["action_permissions"] = _dump_permissions(values["action_permissions"])
    for key, value in values.items():
        setattr(mapping, key, value)
    db.commit()
    db.refresh(mapping)
    return _mapping_to_out(mapping, db)


@router.delete("/permission-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wechat_work_permission_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    mapping = (
        db.query(ExternalPermissionMapping)
        .filter(ExternalPermissionMapping.id == mapping_id, ExternalPermissionMapping.provider == WECHAT_WORK_PROVIDER)
        .first()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="权限映射不存在")
    db.delete(mapping)
    db.commit()
    return None


@router.get("/message-deliveries", response_model=list[MessageDeliveryOut])
def list_wechat_work_message_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    return (
        db.query(MessageDelivery)
        .filter(MessageDelivery.provider == WECHAT_WORK_PROVIDER)
        .order_by(MessageDelivery.id.desc())
        .limit(200)
        .all()
    )


@router.post("/message/test", response_model=list[MessageDeliveryOut])
def send_wechat_work_test_message(
    payload: WechatWorkMessageTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    return dispatch_message_event(
        db,
        MessageEvent(
            event_type="approval.requested",
            org_id=current_user.org_id,
            recipient_user_ids=[payload.recipient_user_id],
            title=payload.title,
            content=payload.content,
            link_url=payload.link_url,
        ),
    )
