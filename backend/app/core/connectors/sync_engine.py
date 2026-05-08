"""DataLink 同步引擎：从连接器拉取数据，写入目标 PostgreSQL 表。"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_datasource_engine
from app.models.data_link import DataLink, DataLinkLog, DataLinkTask

logger = logging.getLogger(__name__)


def _flatten(record: dict) -> dict:
    """Flatten one level of nested dicts/lists into JSON strings."""
    out = {}
    for k, v in record.items():
        if isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False)
        elif v is None:
            out[k] = None
        else:
            out[k] = str(v)
    return out


def _ensure_table(engine, table: str, columns: list[str]) -> None:
    """CREATE TABLE IF NOT EXISTS with all text columns + _sync_at timestamp."""
    col_defs = ",\n  ".join(f'"{c}" TEXT' for c in columns)
    ddl = f"""
    CREATE TABLE IF NOT EXISTS "{table}" (
      {col_defs},
      "_sync_at" TIMESTAMP DEFAULT now()
    )
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _upsert_batch(engine, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    col_list = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    insert_sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'
    with engine.begin() as conn:
        conn.execute(text(insert_sql), rows)
    return len(rows)


def run_sync_task(task_id: int) -> None:
    db: Session = SessionLocal()
    log: DataLinkLog | None = None
    try:
        task = db.query(DataLinkTask).filter(DataLinkTask.id == task_id).first()
        if not task:
            logger.error("DataLink task %d not found", task_id)
            return

        link = db.query(DataLink).filter(DataLink.id == task.link_id).first()
        if not link:
            logger.error("DataLink %d not found", task.link_id)
            return

        log = DataLinkLog(
            task_id=task_id,
            link_id=task.link_id,
            status="running",
            org_id=task.org_id,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        task.last_run_status = "running"
        task.last_run_at = datetime.now(timezone.utc)
        db.commit()

        from app.core.connectors.base import get_connector
        connector = get_connector(link.connector_type, link.config_json or {})

        # Determine target engine
        target_table = task.target_table or f"dl_{link.connector_type}_{task.source_object}"
        if task.target_datasource_id:
            from app.models.datasource import DataSource
            ds = db.query(DataSource).filter(DataSource.id == task.target_datasource_id).first()
            engine = get_datasource_engine(ds.database_url) if ds else None
        else:
            engine = None

        if not engine:
            raise RuntimeError("未配置目标数据源，数据将不会持久化（仅计数）")

        watermark = task.incremental_watermark if task.sync_mode == "incremental" else None

        # Full sync: truncate first
        if task.sync_mode == "full":
            with engine.begin() as conn:
                conn.execute(text(f'TRUNCATE TABLE IF EXISTS "{target_table}"'))

        total_read = 0
        total_written = 0
        last_watermark = watermark
        schema_ensured = False

        for page in connector.fetch_pages(
            task.source_object,
            filters=task.filter_json or {},
            incremental_field=task.incremental_field,
            watermark=watermark,
        ):
            if not page:
                continue
            flat_rows = [_flatten(r) for r in page]
            total_read += len(flat_rows)

            if not schema_ensured:
                _ensure_table(engine, target_table, list(flat_rows[0].keys()))
                schema_ensured = True

            # Apply field mapping if configured
            if task.field_mapping_json:
                mapping = {m["src"]: m["dst"] for m in task.field_mapping_json if m.get("src") and m.get("dst")}
                flat_rows = [{mapping.get(k, k): v for k, v in row.items()} for row in flat_rows]

            written = _upsert_batch(engine, target_table, flat_rows)
            total_written += written

            # Track incremental watermark
            if task.incremental_field and flat_rows:
                last_val = flat_rows[-1].get(task.incremental_field)
                if last_val:
                    last_watermark = str(last_val)

        # Update watermark
        if task.sync_mode == "incremental" and last_watermark:
            task.incremental_watermark = last_watermark

        task.last_run_status = "success"
        task.last_run_records = total_written
        log.status = "success"
        log.records_read = total_read
        log.records_written = total_written
        log.finished_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("DataLink task %d done: read=%d written=%d", task_id, total_read, total_written)

    except Exception as exc:
        logger.exception("DataLink task %d failed: %s", task_id, exc)
        if log:
            log.status = "error"
            log.error_message = str(exc)[:2000]
            log.finished_at = datetime.now(timezone.utc)
        if task:  # noqa: F821 - task defined in try block
            task.last_run_status = "error"
        try:
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
