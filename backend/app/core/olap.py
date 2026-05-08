from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings


_doris_engine: Engine | None = None
_doris_admin_engine: Engine | None = None


@dataclass(frozen=True)
class OlapWriteResult:
    table_name: str
    row_count: int
    mode: str
    watermark: str | None = None
    message: str = ""


def build_doris_sqlalchemy_url(config=settings, include_database: bool = True) -> str:
    user = quote_plus(str(config.doris_user))
    password = quote_plus(str(config.doris_password or ""))
    auth = f"{user}:{password}" if password else user
    database = f"/{config.doris_database}" if include_database else ""
    return (
        f"mysql+pymysql://{auth}@{config.doris_host}:"
        f"{int(config.doris_query_port)}{database}"
    )


def _get_doris_admin_engine() -> Engine:
    global _doris_admin_engine
    if _doris_admin_engine is None:
        _doris_admin_engine = create_engine(
            build_doris_sqlalchemy_url(include_database=False),
            pool_pre_ping=True,
        )
    return _doris_admin_engine


def ensure_doris_database() -> None:
    database = _quote_identifier(settings.doris_database)
    with _get_doris_admin_engine().begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {database}"))


def get_doris_engine() -> Engine:
    global _doris_engine
    if _doris_engine is None:
        ensure_doris_database()
        _doris_engine = create_engine(build_doris_sqlalchemy_url(), pool_pre_ping=True)
    return _doris_engine


def reset_doris_engine() -> None:
    global _doris_engine, _doris_admin_engine
    if _doris_engine is not None:
        _doris_engine.dispose()
    if _doris_admin_engine is not None:
        _doris_admin_engine.dispose()
    _doris_engine = None
    _doris_admin_engine = None


def materialized_table_name(dataset: Any) -> str:
    org_id = getattr(dataset, "org_id", None) or 0
    dataset_id = getattr(dataset, "id", None)
    if not dataset_id:
        raise ValueError("dataset id is required for materialization")
    return f"sb_org_{org_id}_dataset_{dataset_id}"


def _quote_identifier(identifier: str) -> str:
    clean = str(identifier).strip()
    if not clean.replace("_", "").isalnum() or not clean:
        raise ValueError(f"invalid Doris identifier: {identifier}")
    return f"`{clean}`"


def _normalize_columns(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    if columns:
        return [str(column) for column in columns]
    if rows:
        return [str(column) for column in rows[0].keys()]
    return []


def _infer_doris_type(values: list[Any]) -> str:
    non_null_values = [value for value in values if value is not None]
    if not non_null_values:
        return "STRING"
    if all(isinstance(value, bool) for value in non_null_values):
        return "BOOLEAN"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null_values):
        return "BIGINT"
    if all(isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) for value in non_null_values):
        return "DOUBLE"
    if all(isinstance(value, datetime) for value in non_null_values):
        return "DATETIME"
    if all(isinstance(value, date) and not isinstance(value, datetime) for value in non_null_values):
        return "DATE"
    return "STRING"


def _coerce_row(columns: list[str], row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column) for column in columns}


def _max_watermark(rows: list[dict[str, Any]], incremental_key: str | None) -> str | None:
    if not incremental_key:
        return None
    values = [row.get(incremental_key) for row in rows if row.get(incremental_key) is not None]
    if not values:
        return None
    return str(max(values))


def get_olap_status() -> dict[str, Any]:
    status = {
        "enabled": bool(settings.doris_enabled),
        "engine": "Apache Doris",
        "host": settings.doris_host,
        "query_port": settings.doris_query_port,
        "http_port": settings.doris_http_port,
        "database": settings.doris_database,
        "healthy": False,
        "message": "Doris is disabled",
    }
    if not settings.doris_enabled:
        return status
    try:
        with get_doris_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        status["healthy"] = True
        status["message"] = "Doris connection is healthy"
    except Exception as exc:
        status["message"] = str(exc)
    return status


def execute_materialized_dataset_preview(table_name: str, limit: int) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 5000))
    sql = text(f"SELECT * FROM {_quote_identifier(table_name)} LIMIT :limit")
    with get_doris_engine().connect() as conn:
        result = conn.execute(sql, {"limit": safe_limit})
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
    return {"columns": columns, "rows": rows}


def write_dataset_to_olap(
    dataset: Any,
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    mode: str = "full",
    incremental_key: str | None = None,
) -> OlapWriteResult:
    normalized_columns = _normalize_columns(columns, rows)
    if not normalized_columns:
        raise ValueError("dataset has no columns to materialize")

    table_name = getattr(dataset, "materialized_table_name", None) or materialized_table_name(dataset)
    table_identifier = _quote_identifier(table_name)
    first_column = normalized_columns[0]
    column_defs = []
    for column in normalized_columns:
        values = [row.get(column) for row in rows]
        column_defs.append(f"{_quote_identifier(column)} {_infer_doris_type(values)}")

    create_sql = f"""
CREATE TABLE IF NOT EXISTS {table_identifier} (
  {", ".join(column_defs)}
)
DUPLICATE KEY({_quote_identifier(first_column)})
DISTRIBUTED BY HASH({_quote_identifier(first_column)}) BUCKETS 10
PROPERTIES ("replication_num" = "1")
"""
    insert_sql = text(
        f"INSERT INTO {table_identifier} "
        f"({', '.join(_quote_identifier(column) for column in normalized_columns)}) "
        f"VALUES ({', '.join(f':{column}' for column in normalized_columns)})"
    )
    prepared_rows = [_coerce_row(normalized_columns, row) for row in rows]

    with get_doris_engine().begin() as conn:
        conn.execute(text(create_sql))
        if mode == "full":
            conn.execute(text(f"TRUNCATE TABLE {table_identifier}"))
        if prepared_rows:
            conn.execute(insert_sql, prepared_rows)

    watermark = _max_watermark(prepared_rows, incremental_key)
    return OlapWriteResult(
        table_name=table_name,
        row_count=len(prepared_rows),
        mode=mode,
        watermark=watermark,
        message=f"{len(prepared_rows)} rows materialized to Doris",
    )
