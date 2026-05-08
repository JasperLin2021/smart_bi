import html
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.core.external_auth import upsert_wechat_work_user
from app.core.wechat_work import WECHAT_WORK_PROVIDER, WechatWorkClient
from app.db.session import get_db
from app.models.integration import IntegrationConfig
from app.models.user import User
from app.schemas.auth import Token, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/login", response_model=Token)
def login(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username", "")
    password = payload.get("password", "")
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")
    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


def _get_enabled_wechat_work_config(db: Session) -> IntegrationConfig:
    record = db.query(IntegrationConfig).filter(IntegrationConfig.provider == WECHAT_WORK_PROVIDER).first()
    if not (
        record
        and record.enabled
        and record.corp_id
        and record.agent_id
        and record.app_secret
        and record.callback_url
    ):
        raise HTTPException(status_code=400, detail="企业微信登录未配置或未启用")
    return record


def _build_wechat_work_client(record: IntegrationConfig) -> WechatWorkClient:
    return WechatWorkClient(
        corp_id=record.corp_id or "",
        agent_id=record.agent_id or "",
        app_secret=record.app_secret or "",
        callback_url=record.callback_url or "",
    )


@router.get("/wechat-work/login-url")
def get_wechat_work_login_url(db: Session = Depends(get_db)):
    record = _get_enabled_wechat_work_config(db)
    client = _build_wechat_work_client(record)
    return {"login_url": client.build_login_url(secrets.token_urlsafe(16))}


@router.get("/wechat-work/callback", response_class=HTMLResponse)
def wechat_work_callback(
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    record = _get_enabled_wechat_work_config(db)
    client = _build_wechat_work_client(record)
    try:
        access_token = client.get_access_token()
        external_user_id = client.get_user_id_by_code(code, access_token)
        external_user = client.get_user(access_token, external_user_id)
        user = upsert_wechat_work_user(db, corp_id=record.corp_id or "", external_user=external_user)
        token = create_access_token(str(user.id))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"企业微信登录失败: {exc}") from exc

    escaped_token = html.escape(token, quote=True)
    return HTMLResponse(
        f"""
        <!doctype html>
        <html>
          <head><meta charset="utf-8"><title>企业微信登录成功</title></head>
          <body>
            <script>
              localStorage.setItem("smart-bi-token", "{escaped_token}");
              window.location.replace("/dashboard");
            </script>
          </body>
        </html>
        """
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_name = None
    if current_user.org_id:
        from app.models.organization import Organization
        org = db.query(Organization).filter(Organization.id == current_user.org_id).first()
        if org:
            org_name = org.name
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "org_id": current_user.org_id,
        "org_name": org_name,
    }
