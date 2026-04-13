import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.llm_setting import LlmSetting
from app.models.notification_setting import NotificationSetting
from app.models.user import User
from app.schemas.settings import LlmConfigOut, LlmConfigUpdate, LlmConfigTestRequest
from app.schemas.notification_setting import (
    NotificationSettingOut,
    NotificationSettingUpdate,
    NotificationTestRequest,
)
from app.core.llm import (
    get_default_llm_config,
    normalize_llm_config,
    set_llm_config_cache,
    test_llm_connection,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def ensure_admin(user: User):
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限")


def _format_llm_test_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text.strip()
        if body:
            return f"LLM 连接测试失败: {body}"
        return f"LLM 连接测试失败: 上游服务返回 {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return f"LLM 连接测试失败: {exc}"
    return f"LLM 连接测试失败: {exc}"


@router.get("/llm", response_model=LlmConfigOut)
def get_llm_setting(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if not record:
        default_config = normalize_llm_config(get_default_llm_config())
        record = LlmSetting(
            provider=default_config["provider"],
            base_url=default_config["base_url"],
            api_key=default_config["api_key"],
            model=default_config["model"],
            temperature=default_config["temperature"],
            agent_planner_mode="llm_only",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "agent_planner_mode": record.agent_planner_mode or "llm_only",
        "api_key_set": bool(record.api_key),
    }


@router.post("/llm/refresh")
def refresh_llm_cache(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if record:
        set_llm_config_cache(
            normalize_llm_config(
                {
                    "provider": record.provider,
                    "base_url": record.base_url,
                    "api_key": record.api_key,
                    "model": record.model,
                    "temperature": record.temperature,
                    "agent_planner_mode": record.agent_planner_mode or "llm_only",
                }
            )
        )
    return {"status": "ok"}


@router.put("/llm", response_model=LlmConfigOut)
def update_llm_setting(
    payload: LlmConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    record = db.query(LlmSetting).first()
    if not record:
        record = LlmSetting(
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key or "",
            model=payload.model,
            temperature=payload.temperature,
            agent_planner_mode=payload.agent_planner_mode,
        )
        db.add(record)
    else:
        record.provider = payload.provider
        record.base_url = payload.base_url
        record.model = payload.model
        record.temperature = payload.temperature
        record.agent_planner_mode = payload.agent_planner_mode
        if payload.api_key is not None and payload.api_key.strip():
            record.api_key = payload.api_key.strip()
    db.commit()
    db.refresh(record)
    set_llm_config_cache(
        normalize_llm_config(
            {
                "provider": record.provider,
                "base_url": record.base_url,
                "api_key": record.api_key,
                "model": record.model,
                "temperature": record.temperature,
                "agent_planner_mode": record.agent_planner_mode or "llm_only",
            }
        )
    )
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "temperature": record.temperature,
        "agent_planner_mode": record.agent_planner_mode or "llm_only",
        "api_key_set": bool(record.api_key),
    }


@router.get("/notification", response_model=NotificationSettingOut)
def get_notification_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    record = db.query(NotificationSetting).first()
    if not record:
        record = NotificationSetting()
        db.add(record)
        db.commit()
        db.refresh(record)
    return NotificationSettingOut(
        email_enabled=record.email_enabled or False,
        smtp_host=record.smtp_host,
        smtp_port=record.smtp_port or 465,
        smtp_username=record.smtp_username,
        smtp_from=record.smtp_from,
        smtp_use_ssl=record.smtp_use_ssl if record.smtp_use_ssl is not None else True,
        smtp_password_set=bool(record.smtp_password),
        wechat_enabled=record.wechat_enabled or False,
        wechat_webhook_url=record.wechat_webhook_url,
        dingtalk_enabled=record.dingtalk_enabled or False,
        dingtalk_webhook_url=record.dingtalk_webhook_url,
        dingtalk_secret_set=bool(record.dingtalk_secret),
    )


@router.put("/notification", response_model=NotificationSettingOut)
def update_notification_setting(
    payload: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    record = db.query(NotificationSetting).first()
    if not record:
        record = NotificationSetting()
        db.add(record)

    data = payload.model_dump(exclude_unset=True)
    # Never overwrite secrets with None
    for secret_field in ("smtp_password", "dingtalk_secret"):
        if secret_field in data and data[secret_field] is None:
            del data[secret_field]
    for key, value in data.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return NotificationSettingOut(
        email_enabled=record.email_enabled or False,
        smtp_host=record.smtp_host,
        smtp_port=record.smtp_port or 465,
        smtp_username=record.smtp_username,
        smtp_from=record.smtp_from,
        smtp_use_ssl=record.smtp_use_ssl if record.smtp_use_ssl is not None else True,
        smtp_password_set=bool(record.smtp_password),
        wechat_enabled=record.wechat_enabled or False,
        wechat_webhook_url=record.wechat_webhook_url,
        dingtalk_enabled=record.dingtalk_enabled or False,
        dingtalk_webhook_url=record.dingtalk_webhook_url,
        dingtalk_secret_set=bool(record.dingtalk_secret),
    )


@router.post("/notification/test")
def test_notification_channel(
    payload: NotificationTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    record = db.query(NotificationSetting).first()
    if not record:
        raise HTTPException(status_code=400, detail="通知渠道未配置")

    from app.core.alert_notifier import (
        send_wechat_sync,
        send_dingtalk_sync,
        send_email_sync,
    )

    test_msg = "## Smart BI 通知测试\n\n这是一条测试消息，渠道配置正常。"
    test_html = "<h3>Smart BI 通知测试</h3><p>这是一条测试消息，渠道配置正常。</p>"

    channel = payload.channel
    try:
        if channel == "wechat":
            if not (record.wechat_enabled and record.wechat_webhook_url):
                raise HTTPException(status_code=400, detail="企业微信未启用或 Webhook URL 未配置")
            send_wechat_sync(record.wechat_webhook_url, test_msg)

        elif channel == "dingtalk":
            if not (record.dingtalk_enabled and record.dingtalk_webhook_url):
                raise HTTPException(status_code=400, detail="钉钉未启用或 Webhook URL 未配置")
            send_dingtalk_sync(record.dingtalk_webhook_url, record.dingtalk_secret, test_msg)

        elif channel == "email":
            if not (record.email_enabled and record.smtp_host):
                raise HTTPException(status_code=400, detail="邮件未启用或 SMTP 未配置")
            to = (payload.email_to or record.smtp_username or "").strip()
            if not to:
                raise HTTPException(status_code=400, detail="请提供测试收件人邮箱")
            send_email_sync(
                smtp_host=record.smtp_host,
                smtp_port=record.smtp_port or 465,
                smtp_username=record.smtp_username or "",
                smtp_password=record.smtp_password or "",
                smtp_from=record.smtp_from or record.smtp_username or "",
                use_ssl=record.smtp_use_ssl if record.smtp_use_ssl is not None else True,
                recipients=[to],
                subject="[Smart BI] 通知渠道测试",
                html_content=test_html,
            )
        else:
            raise HTTPException(status_code=400, detail=f"未知渠道: {channel}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"发送失败: {exc}") from exc

    return {"status": "ok", "channel": channel}


@router.post("/llm/test")
async def test_llm_setting(
    payload: LlmConfigTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)

    record = db.query(LlmSetting).first()
    api_key = payload.api_key.strip() if payload.api_key and payload.api_key.strip() else ""
    if not api_key and record:
        api_key = record.api_key

    if not api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    config = normalize_llm_config(
        {
            "provider": payload.provider,
            "base_url": payload.base_url.rstrip("/"),
            "api_key": api_key,
            "model": payload.model,
            "temperature": payload.temperature,
            "agent_planner_mode": "llm_only",
        }
    )
    try:
        return await test_llm_connection(config)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_format_llm_test_error(exc)) from exc
