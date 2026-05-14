import base64
import json
import re
from datetime import datetime, timedelta
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api import query as query_api
from app.core.audit import try_record_audit_log
from app.core.config import settings
from app.core.excel_executor import execute_excel_query
from app.core.permissions import has_action_permission, require_menu
from app.core.security import verify_password
from app.db.session import get_db, get_datasource_engine
from app.models.big_screen import BigScreen
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.organization import Organization
from app.models.user import User
from app.schemas.query import QueryAskRequest

router = APIRouter(prefix="/goview", tags=["goview"])
SQL_READ_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE | re.DOTALL)
goview_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _is_loopback_host(hostname: str | None) -> bool:
    return hostname in {"127.0.0.1", "localhost", "::1"}


def _host_without_port(host: str | None) -> str | None:
    if not host:
        return None
    first_host = host.split(",", 1)[0].strip()
    if not first_host:
        return None
    return urlsplit(f"//{first_host}").hostname


def _netloc(hostname: str, port: int | None) -> str:
    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    return f"{host}:{port}" if port else host


def _browser_base_url(request: Request | None = None) -> str:
    configured_embed_url = (settings.goview_embed_base_url or "").rstrip("/")
    internal_url = settings.goview_base_url.rstrip("/")
    request_host = _host_without_port(request.headers.get("x-forwarded-host") if request else None)
    if request_host is None and request:
        request_host = _host_without_port(request.headers.get("host")) or request.url.hostname

    if configured_embed_url:
        configured_host = urlsplit(configured_embed_url).hostname
        if not (_is_loopback_host(configured_host) and request_host and not _is_loopback_host(request_host)):
            return configured_embed_url

    split = urlsplit(internal_url)
    if request_host:
        return urlunsplit(
            (
                split.scheme or "http",
                _netloc(request_host, split.port),
                split.path.rstrip("/"),
                "",
                "",
            )
        ).rstrip("/")
    return configured_embed_url or internal_url


def _service_base_url() -> str:
    return settings.goview_base_url.rstrip("/")


def _service_reachable(url: str) -> bool:
    if url.startswith("/"):
        return True
    opener = urllib_request.build_opener(urllib_request.ProxyHandler({}))
    request = urllib_request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "SmartBI-GoView-Healthcheck/1.0",
        },
    )
    try:
        with opener.open(request, timeout=1.5) as response:
            return 200 <= response.status < 500
    except urllib_error.HTTPError as exc:
        return 200 <= exc.code < 500
    except Exception:
        return False


def _join_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url}/{path.lstrip('/')}"


def _append_query(url: str, values: dict[str, str | int | None]) -> str:
    split = urlsplit(url)
    next_values = {key: str(value) for key, value in values.items() if value is not None}
    if split.fragment:
        fragment_split = urlsplit(split.fragment)
        fragment_query = dict(parse_qsl(fragment_split.query, keep_blank_values=True))
        fragment_query.update(next_values)
        fragment = urlunsplit(
            (
                fragment_split.scheme,
                fragment_split.netloc,
                fragment_split.path,
                urlencode(fragment_query),
                fragment_split.fragment,
            )
        )
        return urlunsplit((split.scheme, split.netloc, split.path, split.query, fragment))

    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.update(next_values)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _organization_payload(db: Session, user: User) -> dict:
    if user.role == "super_admin":
        return {"id": None, "name": "全部组织", "scope": "all"}
    org_name = None
    if user.org_id:
        org = db.query(Organization).filter(Organization.id == user.org_id).first()
        org_name = org.name if org else None
    return {"id": user.org_id, "name": org_name or f"组织 #{user.org_id}", "scope": "org"}


def _goview_auth_secret() -> str:
    return f"goview:{settings.goview_bridge_secret or settings.jwt_secret}"


def _user_from_token_payload(db: Session, payload: dict) -> User:
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def get_goview_current_user(
    token: str = Depends(goview_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, _goview_auth_secret(), algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "goview":
            raise JWTError("invalid goview token scope")
        return _user_from_token_payload(db, payload)
    except HTTPException:
        raise
    except (JWTError, ValueError):
        pass

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") == "goview":
            raise JWTError("goview scoped token cannot use regular auth secret")
        return _user_from_token_payload(db, payload)
    except HTTPException:
        raise
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc


def _goview_token(user: User, modes: list[str], organization: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "org_id": organization.get("id"),
        "scope": "goview",
        "modes": modes,
        "exp": expire,
    }
    return jwt.encode(payload, _goview_auth_secret(), algorithm=settings.jwt_algorithm)


def _allowed_modes(user: User) -> list[str]:
    modes = ["view"] if has_action_permission(user, "goview.read") else []
    if has_action_permission(user, "goview.design"):
        modes.append("design")
    return modes


def _goview_success(data=None, msg: str = "success", **extra) -> dict:
    return {"code": 200, "msg": msg, "data": data, **extra}


def _goview_error(code: int, msg: str, data=None) -> dict:
    return {"code": code, "msg": msg, "data": data}


def _format_time(value) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _screen_meta(screen: BigScreen) -> dict:
    bindings = screen.data_bindings_json or {}
    if not isinstance(bindings, dict):
        return {}
    meta = bindings.get("_goview_meta") or {}
    return meta if isinstance(meta, dict) else {}


def _set_screen_meta(screen: BigScreen, **values) -> None:
    bindings = screen.data_bindings_json if isinstance(screen.data_bindings_json, dict) else {}
    meta = bindings.get("_goview_meta") if isinstance(bindings.get("_goview_meta"), dict) else {}
    for key, value in values.items():
        if value is not None:
            meta[key] = value
    bindings["_goview_meta"] = meta
    screen.data_bindings_json = bindings


def _screen_to_project(screen: BigScreen, *, include_content: bool = False) -> dict:
    meta = _screen_meta(screen)
    project = {
        "id": screen.id,
        "projectName": screen.title,
        "state": 1 if screen.status == "published" else -1,
        "createTime": _format_time(screen.created_at),
        "createUserId": str(screen.owner_id or ""),
        "isDelete": -1,
        "indexImage": meta.get("indexImage"),
        "remarks": screen.description,
    }
    if include_content:
        project["content"] = json.dumps(screen.canvas_json or {}, ensure_ascii=False, default=str)
    return project


def _can_manage_screen(user: User, screen: BigScreen) -> bool:
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and screen.org_id == user.org_id:
        return True
    return screen.owner_id == user.id


def _apply_screen_visibility(query, user: User):
    if user.role == "super_admin":
        return query
    query = query.filter(BigScreen.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(BigScreen.status == "published", BigScreen.owner_id == user.id))


def _get_visible_screen(db: Session, screen_id: int, user: User) -> BigScreen:
    screen = _apply_screen_visibility(db.query(BigScreen), user).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    return screen


def _get_manageable_screen(db: Session, screen_id: int, user: User) -> BigScreen:
    screen = db.query(BigScreen).filter(BigScreen.id == screen_id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="大屏不存在")
    if not _can_manage_screen(user, screen):
        raise HTTPException(status_code=403, detail="无权限")
    return screen


def _require_design(user: User) -> None:
    require_menu(user, "goview.view")
    if not has_action_permission(user, "goview.design"):
        raise HTTPException(status_code=403, detail="无权设计 GoView 大屏")


def _parse_json_content(content: str | None) -> dict:
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"大屏内容不是合法 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="大屏内容必须是 JSON 对象")
    return parsed


def _extract_project_ids(raw_ids) -> list[int]:
    if raw_ids is None:
        return []
    if isinstance(raw_ids, (list, tuple, set)):
        values = raw_ids
    else:
        values = str(raw_ids).split(",")
    ids: list[int] = []
    for value in values:
        text_value = str(value).strip()
        if not text_value:
            continue
        try:
            ids.append(int(text_value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="项目 ID 不合法") from exc
    return ids


def _datasource_query_for_user(db: Session, user: User):
    query = db.query(DataSource).filter(DataSource.is_active == 1)
    if user.role != "super_admin":
        query = query.filter(DataSource.org_id == user.org_id)
    return query


def _get_accessible_datasource(db: Session, datasource_id: int | None, user: User) -> DataSource:
    query = _datasource_query_for_user(db, user)
    if datasource_id:
        datasource = query.filter(DataSource.id == datasource_id).first()
    else:
        datasource = query.order_by(DataSource.id.asc()).first()
    if not datasource:
        raise HTTPException(status_code=404, detail="数据源不存在或无权访问")
    return datasource


def _datasource_to_payload(datasource: DataSource) -> dict:
    schema_metadata = None
    if datasource.schema_metadata:
        try:
            schema_metadata = json.loads(datasource.schema_metadata)
        except (TypeError, json.JSONDecodeError):
            schema_metadata = None
    return {
        "id": datasource.id,
        "name": datasource.name,
        "slug": datasource.slug,
        "source_type": datasource.source_type,
        "metadata_prompt": datasource.metadata_prompt,
        "schema_metadata": schema_metadata,
        "org_id": datasource.org_id,
    }


def _dataset_query_for_user(db: Session, user: User):
    query = db.query(Dataset)
    if user.role == "super_admin":
        return query
    query = query.filter(Dataset.org_id == user.org_id)
    if user.role == "org_admin":
        return query
    return query.filter(or_(Dataset.status == "published", Dataset.owner_id == user.id))


def _dataset_to_payload(dataset: Dataset) -> dict:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "datasource_id": dataset.datasource_id,
        "fields": dataset.fields_json,
        "filters": dataset.filters_json,
        "derived_columns": dataset.derived_columns_json,
        "joins": dataset.joins_json,
        "aggregations": dataset.aggregations_json,
        "status": dataset.status,
        "visibility": dataset.visibility,
        "org_id": dataset.org_id,
    }


def _ensure_read_sql(sql: str) -> str:
    normalized = (sql or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="SQL 不能为空")
    if not SQL_READ_RE.match(normalized):
        raise HTTPException(status_code=400, detail="GoView 数据绑定仅允许 SELECT 查询")
    return normalized


def _execute_read_sql(datasource: DataSource, sql: str) -> dict:
    read_sql = _ensure_read_sql(sql)
    if datasource.source_type == "excel":
        return execute_excel_query(datasource.database_url, read_sql)

    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(read_sql))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
    return {"columns": columns, "rows": rows}


def _goview_dataset_payload(result: dict, *, sql_query: str | None = None, summary: str | None = None) -> dict:
    columns = result.get("columns", []) if isinstance(result, dict) else []
    rows = result.get("rows", []) if isinstance(result, dict) else []
    payload = {
        "dimensions": columns,
        "columns": columns,
        "rows": jsonable_encoder(rows),
        "source": jsonable_encoder(rows),
        "dataset": {
            "dimensions": columns,
            "source": jsonable_encoder(rows),
        },
    }
    if sql_query:
        payload["sql_query"] = sql_query
    if summary:
        payload["summary"] = summary
    return payload


def get_goview_launch(
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request | None = None,
):
    require_menu(current_user, "goview.view")
    modes = _allowed_modes(current_user)
    if not modes:
        raise HTTPException(status_code=403, detail="无权访问 GoView")

    requested_mode = mode or ("design" if "design" in modes else "view")
    if requested_mode not in modes:
        raise HTTPException(status_code=403, detail=f"无权使用 GoView {requested_mode} 模式")

    organization = _organization_payload(db, current_user)
    token = _goview_token(current_user, modes, organization)
    base_url = _browser_base_url(request)
    target_values = {
        "smart_bi_token": token,
        "smart_bi_user": current_user.username,
        "smart_bi_role": current_user.role,
        "smart_bi_org_id": organization.get("id"),
    }
    targets = {
        "view": _append_query(_join_url(base_url, settings.goview_view_path), target_values),
    }
    if "design" in modes:
        targets["design"] = _append_query(_join_url(base_url, settings.goview_design_path), target_values)

    reachable = _service_reachable(_service_base_url())
    result = {
        "enabled": bool(settings.goview_enabled and settings.goview_base_url and reachable),
        "reachable": reachable,
        "title": "大屏中心",
        "modes": modes,
        "default_mode": requested_mode,
        "embed": True,
        "organization": organization,
        "targets": targets,
    }
    try_record_audit_log(
        db,
        actor=current_user,
        action="goview.launch",
        resource_type="goview",
        resource_name="GoView",
        org_id=organization.get("id"),
        message="GoView 大屏入口已打开",
        detail={"mode": requested_mode, "modes": modes, "enabled": result["enabled"], "reachable": reachable},
    )
    return result


@router.get("/launch")
def launch_goview(
    request: Request,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_goview_launch(mode=mode, db=db, current_user=current_user, request=request)


@router.get("/health")
def goview_health(request: Request, current_user: User = Depends(get_goview_current_user)):
    require_menu(current_user, "goview.view")
    base_url = _service_base_url()
    reachable = _service_reachable(base_url)
    return {
        "enabled": bool(settings.goview_enabled and settings.goview_base_url and reachable),
        "reachable": reachable,
        "base_url": settings.goview_base_url,
        "embed_base_url": _browser_base_url(request),
    }


@router.post("/sys/login")
def goview_login(payload: dict = Body(...), db: Session = Depends(get_db)):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")

    modes = _allowed_modes(user)
    if not modes:
        raise HTTPException(status_code=403, detail="无权访问 GoView")
    organization = _organization_payload(db, user)
    token = _goview_token(user, modes, organization)
    return _goview_success(
        {
            "token": {"tokenName": "Authorization", "tokenValue": f"Bearer {token}"},
            "userinfo": {
                "id": user.id,
                "userId": user.id,
                "username": user.username,
                "userName": user.username,
                "nickName": user.username,
                "role": user.role,
                "orgId": user.org_id,
            },
        }
    )


@router.get("/sys/logout")
def goview_logout(current_user: User = Depends(get_goview_current_user)):
    del current_user
    return _goview_success(True)


@router.get("/sys/getOssInfo")
def goview_oss_info(current_user: User = Depends(get_goview_current_user)):
    require_menu(current_user, "goview.view")
    return _goview_success(
        {
            "bucketURL": "",
            "BucketURL": "",
            "OSSUrl": "",
            "ossUrl": "",
        }
    )


@router.get("/project/list")
def list_projects(
    page: int = 1,
    limit: int = 12,
    projectName: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    require_menu(current_user, "goview.view")
    safe_page = max(page, 1)
    safe_limit = max(1, min(limit, 100))
    query = _apply_screen_visibility(db.query(BigScreen), current_user)
    if projectName:
        query = query.filter(BigScreen.title.ilike(f"%{projectName}%"))
    count = query.count()
    items = (
        query.order_by(BigScreen.id.desc())
        .offset((safe_page - 1) * safe_limit)
        .limit(safe_limit)
        .all()
    )
    return _goview_success([_screen_to_project(item) for item in items], count=count)


@router.post("/project/create")
def create_project(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    title = (payload.get("projectName") or payload.get("title") or "未命名大屏").strip()
    screen = BigScreen(
        title=title[:128] or "未命名大屏",
        description=payload.get("remarks") or payload.get("description"),
        canvas_json={},
        data_bindings_json={"_goview_meta": {"indexImage": payload.get("indexImage")}},
        status="draft",
        visibility="private",
        org_id=payload.get("org_id") if current_user.role == "super_admin" and payload.get("org_id") else current_user.org_id,
        owner_id=current_user.id,
    )
    db.add(screen)
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="goview.project.create",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="GoView 大屏已创建",
    )
    return _goview_success({"id": screen.id})


@router.get("/project/getData")
def get_project_data(
    projectId: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    require_menu(current_user, "goview.view")
    screen = _get_visible_screen(db, projectId, current_user)
    return _goview_success(_screen_to_project(screen, include_content=True))


@router.post("/project/save/data")
def save_project_data(
    projectId: str = Form(...),
    content: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    screen = _get_manageable_screen(db, int(projectId), current_user)
    screen.canvas_json = _parse_json_content(content)
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="goview.project.save",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="GoView 大屏内容已保存",
    )
    return _goview_success(True)


@router.post("/project/edit")
def edit_project(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    project_id = payload.get("id") or payload.get("projectId")
    if not project_id:
        raise HTTPException(status_code=400, detail="缺少项目 ID")
    screen = _get_manageable_screen(db, int(project_id), current_user)
    title = payload.get("projectName") or payload.get("title")
    if title is not None:
        screen.title = str(title).strip()[:128] or screen.title
    if "remarks" in payload or "description" in payload:
        screen.description = payload.get("remarks") or payload.get("description")
    if "indexImage" in payload:
        _set_screen_meta(screen, indexImage=payload.get("indexImage"))
    db.commit()
    db.refresh(screen)
    return _goview_success(_screen_to_project(screen))


@router.delete("/project/delete")
def delete_project(
    ids: str | int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    project_ids = _extract_project_ids(ids)
    if not project_ids:
        raise HTTPException(status_code=400, detail="缺少项目 ID")
    deleted = 0
    for project_id in project_ids:
        screen = _get_manageable_screen(db, project_id, current_user)
        db.delete(screen)
        deleted += 1
    db.commit()
    try_record_audit_log(
        db,
        actor=current_user,
        action="goview.project.delete",
        resource_type="big_screen",
        resource_id=",".join(str(item) for item in project_ids),
        org_id=current_user.org_id,
        message="GoView 大屏已删除",
        detail={"deleted": deleted},
    )
    return _goview_success({"deleted": deleted})


@router.put("/project/publish")
def publish_project(
    payload: dict | None = Body(default=None),
    id: int | None = None,
    state: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    payload = payload or {}
    project_id = id if id is not None else payload.get("id") or payload.get("projectId")
    publish_state = state if state is not None else payload.get("state")
    if not project_id:
        raise HTTPException(status_code=400, detail="缺少项目 ID")
    screen = _get_manageable_screen(db, int(project_id), current_user)
    if int(publish_state or -1) == 1:
        screen.status = "published"
        screen.visibility = "org"
    else:
        screen.status = "draft"
        screen.visibility = "private"
    db.commit()
    db.refresh(screen)
    try_record_audit_log(
        db,
        actor=current_user,
        action="goview.project.publish",
        resource_type="big_screen",
        resource_id=screen.id,
        resource_name=screen.title,
        org_id=screen.org_id,
        message="GoView 大屏发布状态已更新",
        detail={"state": publish_state},
    )
    return _goview_success(_screen_to_project(screen))


@router.post("/project/upload")
async def upload_project_file(
    object: UploadFile = File(...),
    current_user: User = Depends(get_goview_current_user),
):
    _require_design(current_user)
    content = await object.read()
    content_type = object.content_type or "application/octet-stream"
    encoded = base64.b64encode(content).decode("ascii")
    fileurl = f"data:{content_type};base64,{encoded}"
    return _goview_success({"fileName": object.filename or "upload", "fileurl": fileurl})


@router.get("/smartbi/datasources")
def list_smartbi_datasources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    require_menu(current_user, "goview.view")
    items = _datasource_query_for_user(db, current_user).order_by(DataSource.id.asc()).all()
    return _goview_success([_datasource_to_payload(item) for item in items])


@router.get("/smartbi/datasets")
def list_smartbi_datasets(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    require_menu(current_user, "goview.view")
    query = _dataset_query_for_user(db, current_user)
    if datasource_id:
        query = query.filter(Dataset.datasource_id == datasource_id)
    items = query.order_by(Dataset.id.desc()).all()
    return _goview_success([_dataset_to_payload(item) for item in items])


@router.post("/smartbi/query")
async def smartbi_query(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_goview_current_user),
):
    require_menu(current_user, "goview.view")
    datasource_id = payload.get("datasource_id") or payload.get("datasourceId")
    datasource = _get_accessible_datasource(db, int(datasource_id) if datasource_id else None, current_user)

    question = (payload.get("question") or "").strip()
    sql = (payload.get("sql") or "").strip()
    if question:
        response = await query_api.ask(
            QueryAskRequest(question=question, mode="explore", datasource_id=datasource.id),
            db=db,
            current_user=current_user,
        )
        response_payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        return _goview_success(
            _goview_dataset_payload(
                response_payload.get("result") or {},
                sql_query=response_payload.get("sql_query"),
                summary=response_payload.get("summary"),
            )
        )
    if not sql:
        raise HTTPException(status_code=400, detail="请提供 SQL 或自然语言问题")

    result = _execute_read_sql(datasource, sql)
    return _goview_success(_goview_dataset_payload(result, sql_query=sql))
