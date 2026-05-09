from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from app.api.routes import api_router
from app.core.cache import init_cache
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.llm import get_default_llm_config, set_llm_config_cache, DEFAULT_TEXT2SQL_PROMPT
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.models.llm_setting import LlmSetting
from app.models.datasource import DataSource
from app.models.organization import Organization
from app.models.pinned_chart import PinnedChart  # noqa: F401
from app.models.agent_run import AgentRun  # noqa: F401
from app.models.alert import Alert  # noqa: F401
from app.models.notification_setting import NotificationSetting  # noqa: F401
from app.models.alert_history import AlertHistory  # noqa: F401
from app.models.scheduled_report import ScheduledReport  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.dataset import Dataset, DatasetRefreshLog  # noqa: F401
from app.models.big_screen import BigScreen  # noqa: F401
from app.models.action_item import ActionItem  # noqa: F401
from app.models.embed_token import EmbedToken  # noqa: F401
from app.models.integration import (  # noqa: F401
    ExternalIdentity,
    ExternalOrgBinding,
    ExternalPermissionMapping,
    IntegrationConfig,
    MessageDelivery,
)


@asynccontextmanager
async def _lifespan(application: FastAPI):
    _startup()
    from app.core.alert_scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)

# Default metadata for Carsem (used for migration only)
_CARSEM_METADATA_PROMPT = """数据库表结构信息：
- detail 表：包含异常详情记录
  - id: 主键
  - sumdatetime: 时间戳
  - line: 产线（如 A线, B线）
  - error_code: 错误代码
  - equipmentid: 设备ID
  - productstep: 工序/step（用户说的step就是productstep字段）
  - totaltimes: 发生次数
  - count: 异常数量

- code 表：包含错误代码定义
  - error_code: 错误代码（主键）
  - alarm_text_chinese: 中文告警内容

业务术语映射：
- step = productstep（工序）
- 设备 = equipmentid
- 告警/alarm = error_code"""

_CARSEM_METRICS_PROMPT = """可用指标：
- count: 异常数量统计
- distinct_error_code: 错误代码种类数"""

_CARSEM_RECOMMEND_QUESTIONS = '["最近一周各产线的异常趋势", "Top 10 告警代码", "各设备异常数量排名"]'


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspect(conn).get_columns(table_name))


def _ensure_column(engine, table_name: str, column_definition: str) -> None:
    column_name = column_definition.strip().split()[0]
    with engine.begin() as conn:
        if _has_column(conn, table_name, column_name):
            return
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))


def startup():
    """Public alias kept for backward compatibility with tests."""
    _startup()


def _startup():
    Base.metadata.create_all(bind=engine)

    # Add email_recipients column to alerts table if missing
    try:
        _ensure_column(engine, "alerts", "email_recipients TEXT")
    except Exception:
        pass

    # Add datasource_id columns to existing tables if missing
    for table in ["query_history", "pinned_charts", "metrics"]:
        try:
            _ensure_column(engine, table, "datasource_id INTEGER")
        except Exception:
            pass

    try:
        _ensure_column(engine, "query_history", "drill_context TEXT")
    except Exception:
        pass

    try:
        _ensure_column(engine, "query_history", "parent_history_id INTEGER")
    except Exception:
        pass

    try:
        _ensure_column(engine, "query_history", "llm_model VARCHAR(128)")
    except Exception:
        pass

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS agent_runs (
                      id SERIAL PRIMARY KEY,
                      user_id INTEGER NOT NULL,
                      route VARCHAR(128) NOT NULL,
                      prompt TEXT NOT NULL,
                      plan_json TEXT NULL,
                      execution_json TEXT NULL,
                      status VARCHAR(32) NOT NULL DEFAULT 'planned',
                      created_at TIMESTAMP DEFAULT NOW(),
                      updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
            )
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_id ON agent_runs (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_runs_user_id ON agent_runs (user_id)"))
    except Exception:
        pass

    # Add source_type column to datasources table if missing
    try:
        _ensure_column(engine, "datasources", "source_type VARCHAR(32) DEFAULT 'database'")
    except Exception:
        pass

    # Add org_id column to users table if missing
    try:
        _ensure_column(engine, "users", "org_id INTEGER")
    except Exception:
        pass

    # Add permission columns to users table if missing
    for column_definition in [
        "department VARCHAR(64)",
        "data_scope VARCHAR(32)",
        "permission_override_enabled BOOLEAN DEFAULT 0",
        "menu_permissions TEXT",
        "action_permissions TEXT",
    ]:
        try:
            _ensure_column(engine, "users", column_definition)
        except Exception:
            pass

    # Add org_id column to datasources table if missing
    try:
        _ensure_column(engine, "datasources", "org_id INTEGER")
    except Exception:
        pass

    # Add drill_config column to datasources table if missing
    try:
        _ensure_column(engine, "datasources", "drill_config TEXT")
    except Exception:
        pass

    try:
        _ensure_column(
            engine,
            "llm_settings",
            "agent_planner_mode VARCHAR(32) DEFAULT 'llm_only'",
        )
    except Exception:
        pass

    for column_definition in [
        "is_public INTEGER DEFAULT 0",
        "share_token VARCHAR(64)",
        "shared_user_ids JSON",
        "version INTEGER DEFAULT 1",
    ]:
        try:
            _ensure_column(engine, "dashboards", column_definition)
        except Exception:
            pass

    for column_definition in [
        "pipeline_json JSON",
        "semantic_model_json JSON",
        "last_refresh_status VARCHAR(32)",
        "last_refresh_at TIMESTAMP",
        "last_refresh_row_count INTEGER DEFAULT 0",
        "materialization_status VARCHAR(32)",
        "materialization_mode VARCHAR(32)",
        "materialized_table_name VARCHAR(128)",
        "materialized_at TIMESTAMP",
        "incremental_key VARCHAR(128)",
        "incremental_watermark VARCHAR(256)",
        "materialization_message TEXT",
    ]:
        try:
            _ensure_column(engine, "datasets", column_definition)
        except Exception:
            pass

    for column_definition in [
        "certification_status VARCHAR(32) DEFAULT 'draft'",
        "certified_by VARCHAR(128)",
        "certified_at TIMESTAMP",
        "caliber_version VARCHAR(64) DEFAULT 'v1'",
        "data_updated_at TIMESTAMP",
        "quality_status VARCHAR(32) DEFAULT 'unknown'",
        "quality_message TEXT",
    ]:
        try:
            _ensure_column(engine, "metrics", column_definition)
        except Exception:
            pass

    init_cache()
    db: Session = SessionLocal()

    # === RBAC Seed Data ===
    # Create organizations
    org_nexteer = db.query(Organization).filter(Organization.slug == "nexteer").first()
    if not org_nexteer:
        org_nexteer = Organization(name="Nexteer", slug="nexteer")
        db.add(org_nexteer)
        db.commit()
        db.refresh(org_nexteer)

    org_carsem = db.query(Organization).filter(Organization.slug == "carsem").first()
    if not org_carsem:
        org_carsem = Organization(name="嘉盛半导体", slug="carsem")
        db.add(org_carsem)
        db.commit()
        db.refresh(org_carsem)

    # Ensure admin user (super_admin)
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            role="super_admin",
            org_id=None,
        )
        db.add(admin_user)
        db.commit()
    else:
        # Update existing admin to super_admin
        if admin_user.role != "super_admin":
            admin_user.role = "super_admin"
            admin_user.org_id = None
            db.commit()

    # Create org users
    seed_users = [
        ("nexteer_admin", "nexteer123", "org_admin", org_nexteer.id),
        ("nexteer_certifier", "certifier123", "org_admin", org_nexteer.id),
        ("nexteer", "nexteer123", "user", org_nexteer.id),
        ("carsem_admin", "carsem123", "org_admin", org_carsem.id),
        ("carsem_certifier", "certifier123", "org_admin", org_carsem.id),
        ("carsem", "carsem123", "user", org_carsem.id),
    ]
    for uname, pwd, role, oid in seed_users:
        if not db.query(User).filter(User.username == uname).first():
            db.add(User(
                username=uname,
                hashed_password=get_password_hash(pwd),
                role=role,
                org_id=oid,
            ))
    db.commit()

    # Ensure LLM settings
    llm_record = db.query(LlmSetting).first()
    if not llm_record:
        default_config = get_default_llm_config()
        llm_record = LlmSetting(
            provider=default_config["provider"],
            base_url=default_config["base_url"],
            api_key=default_config["api_key"],
            model=default_config["model"],
            temperature=default_config["temperature"],
            agent_planner_mode=default_config.get("agent_planner_mode", "llm_only"),
        )
        db.add(llm_record)
        db.commit()
        db.refresh(llm_record)
    elif not getattr(llm_record, "agent_planner_mode", None):
        llm_record.agent_planner_mode = "llm_only"
        db.commit()

    set_llm_config_cache(
        {
            "provider": llm_record.provider,
            "base_url": llm_record.base_url,
            "api_key": llm_record.api_key,
            "model": llm_record.model,
            "temperature": llm_record.temperature,
            "agent_planner_mode": llm_record.agent_planner_mode or "llm_only",
        }
    )

    # Migrate: create default Carsem datasource if no datasources exist
    if not db.query(DataSource).first():
        # Try to get metadata from old llm_settings columns (migration path)
        metadata = _CARSEM_METADATA_PROMPT
        metrics = _CARSEM_METRICS_PROMPT
        try:
            row = db.execute(
                text("SELECT metadata_prompt, metrics_prompt FROM llm_settings LIMIT 1")
            ).first()
            if row and row[0]:
                metadata = row[0]
            if row and row[1]:
                metrics = row[1]
        except Exception:
            db.rollback()  # Rollback failed transaction

        ds = DataSource(
            name="嘉盛半导体",
            slug="carsem",
            database_url=settings.database_url,
            metadata_prompt=metadata,
            metrics_prompt=metrics,
            recommend_questions=_CARSEM_RECOMMEND_QUESTIONS,
            org_id=org_carsem.id,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)

        # Set datasource_id on existing records
        try:
            for table in ["query_history", "pinned_charts", "metrics"]:
                db.execute(
                    text(f"UPDATE {table} SET datasource_id = :ds_id WHERE datasource_id IS NULL"),
                    {"ds_id": ds.id},
                )
            db.commit()
        except Exception:
            db.rollback()

    # Assign org_id to existing datasources without org_id
    carsem_ds = db.query(DataSource).filter(DataSource.slug == "carsem").first()
    if carsem_ds and not carsem_ds.org_id:
        carsem_ds.org_id = org_carsem.id
        db.commit()

    # Assign Excel datasource to carsem org
    excel_ds = db.query(DataSource).filter(DataSource.source_type == "excel").first()
    if excel_ds and not excel_ds.org_id:
        excel_ds.org_id = org_carsem.id
        db.commit()

    db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
