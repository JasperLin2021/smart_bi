from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
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
from app.models.pinned_chart import PinnedChart  # noqa: F401

app = FastAPI(title=settings.app_name)

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


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    # Add datasource_id columns to existing tables if missing
    with engine.begin() as conn:
        for table in ["query_history", "pinned_charts", "metrics"]:
            try:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS datasource_id INTEGER")
                )
            except Exception:
                pass

    init_cache()
    db: Session = SessionLocal()

    # Ensure admin user
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        db.add(
            User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                role="admin",
            )
        )
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
        )
        db.add(llm_record)
        db.commit()
        db.refresh(llm_record)

    set_llm_config_cache(
        {
            "provider": llm_record.provider,
            "base_url": llm_record.base_url,
            "api_key": llm_record.api_key,
            "model": llm_record.model,
            "temperature": llm_record.temperature,
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
            pass

        ds = DataSource(
            name="嘉盛半导体",
            slug="carsem",
            database_url=settings.database_url,
            metadata_prompt=metadata,
            metrics_prompt=metrics,
            recommend_questions=_CARSEM_RECOMMEND_QUESTIONS,
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

    db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
