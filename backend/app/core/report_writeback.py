from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validated_identifier(value: Any, label: str) -> str:
    identifier = str(value or "").strip()
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"回写配置中的{label}不合法: {value!r}")
    return identifier


def has_writeback_target(schema: dict[str, Any]) -> bool:
    writeback = schema.get("writeback")
    return isinstance(writeback, dict) and bool(str(writeback.get("table") or "").strip())


def _column_mapping(schema: dict[str, Any]) -> dict[str, str]:
    """payload 字段名 -> 目标列名。列名只能来自模板配置（白名单），不接受用户输入。"""
    writeback = schema.get("writeback") if isinstance(schema.get("writeback"), dict) else {}
    raw_columns = writeback.get("columns")
    mapping: dict[str, str] = {}
    if isinstance(raw_columns, dict):
        for key, column in raw_columns.items():
            mapping[str(key)] = _validated_identifier(column, "列名")
    else:
        for field in schema.get("fields", []):
            if not isinstance(field, dict) or not field.get("name"):
                continue
            mapping[str(field["name"])] = _validated_identifier(field.get("column") or field["name"], "列名")
    return mapping


def execute_fill_writeback(db: Session, schema: dict[str, Any], payload: dict[str, Any]) -> None:
    """按 fill_schema_json 的 writeback 配置把填报数据插入目标表。

    表名/列名仅取自模板配置并做标识符白名单校验 + 方言引号转义，
    值一律走参数绑定，杜绝 SQL 注入。目标表在当前应用库会话内写入，
    与填报记录状态更新处于同一事务。
    """
    writeback = schema.get("writeback") if isinstance(schema.get("writeback"), dict) else {}
    table = _validated_identifier(writeback.get("table"), "表名")
    mapping = _column_mapping(schema)
    if not mapping:
        raise ValueError("回写配置缺少列映射")

    columns = list(mapping.values())
    params = {f"v{index}": payload.get(key) for index, key in enumerate(mapping.keys())}
    preparer = db.get_bind().dialect.identifier_preparer
    quoted_columns = ", ".join(preparer.quote(column) for column in columns)
    placeholders = ", ".join(f":v{index}" for index in range(len(columns)))
    db.execute(
        text(f"INSERT INTO {preparer.quote(table)} ({quoted_columns}) VALUES ({placeholders})"),
        params,
    )
