import re
from typing import Any

import pandas as pd

from app.core.excel_executor import _normalize_table_name
from app.core.excel_uploads import resolve_excel_source_path


SQL_ALIAS_STOPWORDS = {
    "group",
    "order",
    "where",
    "join",
    "on",
    "limit",
    "having",
    "select",
    "union",
}


def _extract_aliases(sql: str) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    pattern = re.compile(
        r"\b(from|join)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:as\s+)?([A-Za-z_][A-Za-z0-9_]*)?",
        re.I,
    )
    for _, table, alias in pattern.findall(sql):
        if alias.lower() in SQL_ALIAS_STOPWORDS:
            alias = ""
        alias_map[(alias or table).lower()] = table.lower()
    return alias_map


def _extract_join_conditions(sql: str) -> list[str]:
    pattern = re.compile(
        r"\bjoin\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:as\s+[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)?\s+on\s+(.*?)(?=\bjoin\b|\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)",
        re.I | re.S,
    )
    return [part.strip() for part in pattern.findall(sql)]


def _extract_join_key_pairs(sql: str) -> list[tuple[str, str, str, str]]:
    pairs: list[tuple[str, str, str, str]] = []
    for condition in _extract_join_conditions(sql):
        matches = re.findall(
            r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
            condition,
            re.I,
        )
        for left_alias, left_col, right_alias, right_col in matches:
            pairs.append(
                (
                    left_alias.lower(),
                    left_col,
                    right_alias.lower(),
                    right_col,
                )
            )
    return pairs


def _extract_alias_column_refs(sql: str) -> list[tuple[str, str]]:
    refs = re.findall(
        r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        re.I,
    )
    return [(alias.lower(), col) for alias, col in refs]


def _strip_join_conditions(sql: str) -> str:
    return re.sub(
        r"\bjoin\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:as\s+[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)?\s+on\s+.*?(?=\bjoin\b|\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)",
        "",
        sql,
        flags=re.I | re.S,
    )


def _load_excel_table_columns(file_path: str) -> dict[str, set[str]]:
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    table_columns: dict[str, set[str]] = {}
    for sheet_name in xlsx.sheet_names:
        table_name = _normalize_table_name(sheet_name)
        df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=0)
        table_columns[table_name.lower()] = {str(col) for col in df.columns}
    return table_columns


def _load_column_values(file_path: str, table_name: str, column_name: str) -> set[Any]:
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    for sheet_name in xlsx.sheet_names:
        normalized = _normalize_table_name(sheet_name).lower()
        if normalized != table_name.lower():
            continue
        df = pd.read_excel(xlsx, sheet_name=sheet_name, usecols=[column_name])
        return {
            value
            for value in df[column_name].dropna().tolist()
            if value != "" and str(value).upper() != "NULL"
        }
    return set()


def detect_excel_join_risk(file_path: str, sql: str) -> dict[str, str] | None:
    alias_map = _extract_aliases(sql)
    table_columns = _load_excel_table_columns(file_path)
    alias_map = {
        alias: table
        for alias, table in alias_map.items()
        if table in table_columns
    }
    if len(set(alias_map.values())) < 2:
        return None

    join_pairs = _extract_join_key_pairs(sql)
    for left_alias, left_col, right_alias, right_col in join_pairs:
        left_table = alias_map.get(left_alias)
        right_table = alias_map.get(right_alias)
        if not left_table or not right_table:
            continue
        if left_table == right_table:
            continue

        left_values = _load_column_values(file_path, left_table, left_col)
        right_values = _load_column_values(file_path, right_table, right_col)
        if left_values and right_values and not (left_values & right_values):
            return {
                "message": (
                    f"{left_table}.{left_col} 与 {right_table}.{right_col} "
                    "在当前 Excel 数据中没有可匹配的取值，继续使用这条 JOIN 路径大概率会返回空结果。"
                ),
                "hint": (
                    f"不要使用 {left_table}.{left_col} = {right_table}.{right_col} 这条 JOIN 路径。"
                    "如果问题涉及的不良类型、工站或不良数量字段已经存在于单表中，优先使用单表查询。"
                ),
            }

    base_alias = next(iter(alias_map))
    base_table = alias_map[base_alias]
    base_columns = table_columns.get(base_table, set())
    if not base_columns:
        return None

    duplicate_column_refs: list[str] = []
    usage_sql = _strip_join_conditions(sql)
    for alias, column in _extract_alias_column_refs(usage_sql):
        if alias == base_alias:
            continue
        joined_table = alias_map.get(alias)
        if not joined_table:
            continue
        if joined_table == base_table:
            continue
        if column in base_columns and column in table_columns.get(joined_table, set()):
            duplicate_column_refs.append(f"{joined_table}.{column}")

    if duplicate_column_refs:
        duplicate_text = "、".join(sorted(set(duplicate_column_refs)))
        return {
            "message": (
                f"SQL 从关联表读取了 {duplicate_text}，但这些字段在主表 {base_table} 中也存在。"
                "这类 JOIN 很可能是多余的，并且会放大空关联风险。"
            ),
            "hint": (
                f"优先使用主表 {base_table} 中已有的同名字段，避免为了获取重复字段而额外 JOIN。"
            ),
        }

    return None
