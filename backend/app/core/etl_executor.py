from __future__ import annotations

import ast
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from sqlalchemy import text

from app.db.session import get_datasource_engine
from app.models.data_pipeline import DataPipeline, DataQualityRule
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.schemas.pipeline import PipelineRunRequest


QualityEvaluator = Callable[[list[DataQualityRule], list[dict[str, Any]], DataSource, datetime], list[dict[str, Any]]]
DatasetExtractor = Callable[[Dataset, DataSource], dict[str, Any]]
DatasetResolver = Callable[[int], tuple[Dataset, DataSource]]
DatasourceResolver = Callable[[int], DataSource]
MetadataExtractor = Callable[[DataSource, dict[str, Any]], dict[str, Any]]


SAFE_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SUPPORTED_NODE_TYPES = {"source", "extract", "metadata_extract", "transform", "join", "union", "sql", "quality", "load", "sink", "reverse_etl"}


@dataclass
class EtlExecutionResult:
    status: str
    columns: list[str]
    rows: list[dict[str, Any]]
    node_logs: dict[str, Any]
    records_read: int
    records_written: int
    records_failed: int
    error_message: str | None = None


def _columns_for(rows: list[dict[str, Any]], fallback: list[str] | None = None) -> list[str]:
    if rows:
        return [str(key) for key in rows[0].keys()]
    return list(fallback or [])


def _preview_rows(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return rows[: max(0, min(int(limit), 20))]


def _node_config(node: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config")
    return config if isinstance(config, dict) else {}


def _topological_nodes(dag: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node for node in dag.get("nodes", []) if isinstance(node, dict)]
    by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    order = {node_id: index for index, node_id in enumerate(by_id)}
    adjacency = {node_id: [] for node_id in by_id}
    in_degree = {node_id: 0 for node_id in by_id}
    for edge in dag.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in by_id or target not in by_id:
            continue
        adjacency[source].append(target)
        in_degree[target] += 1
    queue = sorted([node_id for node_id, degree in in_degree.items() if degree == 0], key=lambda item: order[item])
    result: list[dict[str, Any]] = []
    while queue:
        node_id = queue.pop(0)
        result.append(by_id[node_id])
        for target in sorted(adjacency[node_id], key=lambda item: order[item]):
            in_degree[target] -= 1
            if in_degree[target] == 0:
                queue.append(target)
        queue.sort(key=lambda item: order[item])
    return result if len(result) == len(by_id) else nodes


def _upstream_node_ids(dag: dict[str, Any]) -> dict[str, list[str]]:
    nodes = {str(node.get("id")) for node in dag.get("nodes", []) if isinstance(node, dict) and node.get("id")}
    upstream = {node_id: [] for node_id in nodes}
    for edge in dag.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source in nodes and target in nodes:
            upstream[target].append(source)
    return upstream


def _row_value(row: dict[str, Any], field: str) -> Any:
    if field in row:
        return row[field]
    lowered = {str(key).lower(): key for key in row}
    key = lowered.get(field.lower()) or lowered.get(field.split(".")[-1].lower())
    return row.get(key) if key is not None else None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _convert_value(value: Any, target_type: str) -> Any:
    if value is None:
        return None
    kind = target_type.lower()
    if kind in {"string", "str", "text"}:
        return str(value)
    if kind in {"int", "integer", "bigint"}:
        numeric = _to_decimal(value)
        return int(numeric) if numeric is not None else None
    if kind in {"float", "double", "decimal", "number"}:
        numeric = _to_decimal(value)
        return float(numeric) if numeric is not None else None
    if kind in {"bool", "boolean"}:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}
    if kind in {"date", "datetime", "timestamp"}:
        if isinstance(value, (date, datetime)):
            return value
        text_value = str(value).strip().replace("Z", "+00:00")
        for candidate in (text_value, text_value.replace(" ", "T")):
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.date() if kind == "date" else parsed
            except ValueError:
                continue
        return value
    return value


def _compare(value: Any, operator: str, expected: Any) -> bool:
    op = operator.lower()
    if op in {"in", "not_in"}:
        values = expected if isinstance(expected, list) else [expected]
        result = value in values
        return not result if op == "not_in" else result
    if op in {"is_null", "is null"}:
        return value is None or value == ""
    if op in {"not_null", "is not null"}:
        return value is not None and value != ""
    if op in {"contains"}:
        return str(expected) in str(value or "")
    left_decimal = _to_decimal(value)
    right_decimal = _to_decimal(expected)
    left = left_decimal if left_decimal is not None and right_decimal is not None else value
    right = right_decimal if left_decimal is not None and right_decimal is not None else expected
    if op in {"=", "eq"}:
        return left == right
    if op in {"!=", "ne"}:
        return left != right
    if op in {">", "gt"}:
        return left > right
    if op in {">=", "gte"}:
        return left >= right
    if op in {"<", "lt"}:
        return left < right
    if op in {"<=", "lte"}:
        return left <= right
    return True


def _apply_mapping(rows: list[dict[str, Any]], mapping_items: list[Any]) -> list[dict[str, Any]]:
    if not mapping_items:
        return rows
    output = []
    for row in rows:
        next_row = dict(row)
        for item in mapping_items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or item.get("src") or "").strip()
            target = str(item.get("target") or item.get("dst") or "").strip()
            if not source or not target or source not in next_row:
                continue
            next_row[target] = next_row[source]
            if target != source:
                next_row.pop(source, None)
        output.append(next_row)
    return output


def _apply_type_conversions(rows: list[dict[str, Any]], conversions: list[Any]) -> list[dict[str, Any]]:
    if not conversions:
        return rows
    output = []
    for row in rows:
        next_row = dict(row)
        for item in conversions:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or "").strip()
            target_type = str(item.get("type") or item.get("target_type") or "").strip()
            if field and target_type and field in next_row:
                next_row[field] = _convert_value(next_row[field], target_type)
        output.append(next_row)
    return output


def _apply_filters(rows: list[dict[str, Any]], filters: list[Any]) -> list[dict[str, Any]]:
    if not filters:
        return rows
    output = []
    for row in rows:
        passed = True
        for item in filters:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or item.get("column") or "").strip()
            operator = str(item.get("operator") or item.get("op") or "=").strip()
            if field and not _compare(_row_value(row, field), operator, item.get("value")):
                passed = False
                break
        if passed:
            output.append(row)
    return output


def _safe_eval_expression(expression: str, row: dict[str, Any]) -> Any:
    tree = ast.parse(expression, mode="eval")

    def eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return _row_value(row, node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = eval_node(node.operand)
            return +value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right if right != 0 else None
            return left % right if right != 0 else None
        raise ValueError("unsupported expression")

    return eval_node(tree)


def _apply_derived_columns(rows: list[dict[str, Any]], derived_items: list[Any]) -> list[dict[str, Any]]:
    if not derived_items:
        return rows
    output = []
    for row in rows:
        next_row = dict(row)
        for item in derived_items:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("field") or "").strip()
                expression = str(item.get("expression") or "").strip()
            else:
                text_item = str(item)
                name, expression = [part.strip() for part in text_item.split("=", 1)] if "=" in text_item else ("", "")
            if name and expression and SAFE_TABLE_RE.match(name):
                next_row[name] = _safe_eval_expression(expression, next_row)
        output.append(next_row)
    return output


def _apply_dedupe(rows: list[dict[str, Any]], dedupe: dict[str, Any]) -> list[dict[str, Any]]:
    keys = dedupe.get("keys") if isinstance(dedupe, dict) else None
    if not isinstance(keys, list) or not keys:
        return rows
    keep = str(dedupe.get("keep") or "first").lower()
    ordered = rows if keep != "last" else list(reversed(rows))
    seen: set[tuple[Any, ...]] = set()
    output = []
    for row in ordered:
        signature = tuple(_row_value(row, str(key)) for key in keys)
        if signature in seen:
            continue
        seen.add(signature)
        output.append(row)
    return output if keep != "last" else list(reversed(output))


def _metric_value(values: list[Any], function: str) -> Any:
    fn = function.lower()
    numeric_values = [float(value) for value in values if _to_decimal(value) is not None]
    non_null_values = [value for value in values if value is not None]
    if fn == "count":
        return len(non_null_values)
    if fn == "sum":
        return float(sum(numeric_values))
    if fn == "avg":
        return float(sum(numeric_values) / len(numeric_values)) if numeric_values else None
    if fn == "min":
        return min(numeric_values) if numeric_values else None
    if fn == "max":
        return max(numeric_values) if numeric_values else None
    return None


def _apply_aggregations(rows: list[dict[str, Any]], aggregations: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(aggregations, dict) or not aggregations:
        return rows
    group_by = [str(item) for item in aggregations.get("group_by", []) if str(item).strip()]
    metrics = [item for item in aggregations.get("metrics", []) if isinstance(item, dict)]
    if not metrics:
        return rows
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(_row_value(row, field) for field in group_by)
        groups.setdefault(key, []).append(row)
    output = []
    for key, group_rows in groups.items():
        next_row = {field: key[index] for index, field in enumerate(group_by)}
        for metric in metrics:
            field = str(metric.get("field") or "").strip()
            function = str(metric.get("function") or metric.get("fn") or "sum").strip().lower()
            alias = str(metric.get("alias") or f"{field}_{function}").strip()
            next_row[alias] = _metric_value([_row_value(row, field) for row in group_rows], function)
        output.append(next_row)
    return output


def _execute_transform(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    result = _apply_mapping(rows, config.get("field_mapping") or config.get("mappings") or [])
    result = _apply_type_conversions(result, config.get("type_conversions") or [])
    result = _apply_filters(result, config.get("filters") or [])
    result = _apply_derived_columns(result, config.get("derived_columns") or [])
    result = _apply_dedupe(result, config.get("dedupe") or {})
    result = _apply_aggregations(result, config.get("aggregations") or {})
    return result


def _node_input_rows(
    node_id: str,
    upstream: dict[str, list[str]],
    rowsets_by_node: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    parents = upstream.get(node_id) or []
    if not parents:
        return []
    return [dict(row) for row in rowsets_by_node.get(parents[0], [])]


def _node_input_columns(
    node_id: str,
    upstream: dict[str, list[str]],
    columns_by_node: dict[str, list[str]],
) -> list[str]:
    parents = upstream.get(node_id) or []
    if not parents:
        return []
    return list(columns_by_node.get(parents[0], []))


def _dedupe_rows(rows: list[dict[str, Any]], keys: list[str] | None = None) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    output = []
    for row in rows:
        signature = tuple(_row_value(row, key) for key in keys) if keys else tuple(sorted(row.items()))
        if signature in seen:
            continue
        seen.add(signature)
        output.append(row)
    return output


def _execute_union(rowsets: list[list[dict[str, Any]]], config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for rowset in rowsets for row in rowset]
    if str(config.get("mode") or "all").lower() == "distinct":
        keys = [str(item) for item in config.get("keys", []) if str(item).strip()] if isinstance(config.get("keys"), list) else []
        rows = _dedupe_rows(rows, keys or None)
    return rows


def _prefixed_row(row: dict[str, Any], prefix: str, existing_keys: set[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        target = str(key)
        if target in existing_keys:
            target = f"{prefix}_{target}"
        output[target] = value
    return output


def _execute_join(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    left_key = str(config.get("left_key") or config.get("key") or "").strip()
    right_key = str(config.get("right_key") or config.get("key") or "").strip()
    if not left_key or not right_key:
        raise ValueError("join node requires left_key and right_key")
    join_type = str(config.get("join_type") or config.get("type") or "inner").lower()
    if join_type not in {"inner", "left", "right", "outer", "full"}:
        raise ValueError(f"unsupported join_type: {join_type}")

    right_index: dict[Any, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(right_rows):
        right_index.setdefault(_row_value(row, right_key), []).append((index, row))

    output: list[dict[str, Any]] = []
    matched_right: set[int] = set()
    right_columns = set().union(*(row.keys() for row in right_rows)) if right_rows else set()
    left_columns = set().union(*(row.keys() for row in left_rows)) if left_rows else set()
    for left_row in left_rows:
        matches = right_index.get(_row_value(left_row, left_key), [])
        if not matches:
            if join_type in {"left", "outer", "full"}:
                null_right = {key if key not in left_row else f"right_{key}": None for key in right_columns}
                output.append({**left_row, **null_right})
            continue
        for right_index_value, right_row in matches:
            matched_right.add(right_index_value)
            output.append({**left_row, **_prefixed_row(right_row, "right", set(left_row.keys()))})

    if join_type in {"right", "outer", "full"}:
        for index, right_row in enumerate(right_rows):
            if index in matched_right:
                continue
            null_left = {key: None for key in left_columns}
            output.append({**null_left, **_prefixed_row(right_row, "right", set(null_left.keys()))})
    return output


def _parse_sortable_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text_value = str(value).strip().replace("Z", "+00:00")
    for candidate in (text_value, text_value.replace(" ", "T")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return value


def _filter_incremental_rows(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    payload: PipelineRunRequest,
    dataset: Dataset,
) -> list[dict[str, Any]]:
    mode = str(config.get("mode") or payload.mode or "").lower()
    incremental_key = str(config.get("incremental_key") or getattr(dataset, "incremental_key", None) or "").strip()
    if not incremental_key or mode not in {"incremental", "backfill"} and not payload.window_start and not payload.window_end:
        return rows

    lower = payload.window_start or _parse_sortable_datetime(getattr(dataset, "incremental_watermark", None))
    upper = payload.window_end
    output = []
    for row in rows:
        value = _parse_sortable_datetime(_row_value(row, incremental_key))
        if lower is not None and value is not None and value <= lower:
            continue
        if upper is not None and value is not None and value > upper:
            continue
        output.append(row)
    return output


def _update_incremental_watermark(dataset: Dataset, rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    incremental_key = str(config.get("incremental_key") or getattr(dataset, "incremental_key", None) or "").strip()
    if not incremental_key or not rows:
        return
    values = [_parse_sortable_datetime(_row_value(row, incremental_key)) for row in rows]
    values = [value for value in values if value is not None]
    if values:
        watermark = max(values)
        dataset.incremental_key = incremental_key
        dataset.incremental_watermark = watermark.isoformat() if isinstance(watermark, datetime) else str(watermark)


def _default_metadata_extract(datasource: DataSource, config: dict[str, Any]) -> dict[str, Any]:
    engine = get_datasource_engine(datasource.database_url)
    requested_tables = [str(item) for item in config.get("tables", []) if str(item).strip()] if isinstance(config.get("tables"), list) else []
    rows: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    from sqlalchemy import inspect

    inspector = inspect(engine)
    table_names = requested_tables or inspector.get_table_names()
    for table_name in table_names:
        columns = []
        for column in inspector.get_columns(table_name):
            column_item = {
                "name": column["name"],
                "type": str(column.get("type") or ""),
                "nullable": bool(column.get("nullable", True)),
            }
            columns.append(column_item)
            rows.append(
                {
                    "datasource_id": datasource.id,
                    "table_name": table_name,
                    "column_name": column_item["name"],
                    "data_type": column_item["type"],
                    "nullable": column_item["nullable"],
                }
            )
        tables.append({"name": table_name, "columns": columns})
    schema_metadata = {"datasource_id": datasource.id, "tables": tables}
    if config.get("refresh_schema", True):
        datasource.schema_metadata = json.dumps(schema_metadata, ensure_ascii=False)
    return {
        "columns": ["datasource_id", "table_name", "column_name", "data_type", "nullable"],
        "rows": rows,
        "schema_metadata": schema_metadata,
    }


def _quote_identifier(engine, identifier: str) -> str:
    if not SAFE_TABLE_RE.match(identifier):
        raise ValueError(f"invalid identifier: {identifier}")
    return engine.dialect.identifier_preparer.quote(identifier)


def _sql_type_for(values: list[Any]) -> str:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return "TEXT"
    if all(isinstance(value, bool) for value in non_null):
        return "BOOLEAN"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null):
        return "INTEGER"
    if all(isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) for value in non_null):
        return "REAL"
    return "TEXT"


def _assert_select_sql(sql: str) -> str:
    cleaned = sql.strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    lowered = re.sub(r"/\*.*?\*/|--.*?$", "", cleaned, flags=re.DOTALL | re.MULTILINE).strip().lower()
    if not lowered:
        raise ValueError("SQL node requires a SELECT statement")
    if ";" in lowered:
        raise ValueError("SQL node accepts a single SELECT statement only")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("SQL node only supports SELECT queries")
    blocked = r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|detach|vacuum|pragma)\b"
    if re.search(blocked, lowered):
        raise ValueError("SQL node only supports read-only SELECT queries")
    return cleaned


def _sqlite_quote_identifier(identifier: str) -> str:
    if not SAFE_TABLE_RE.match(identifier):
        raise ValueError(f"invalid identifier: {identifier}")
    return f'"{identifier}"'


def _safe_sqlite_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _sql_row_value(row: dict[str, Any], column: str) -> Any:
    if column in row:
        return row[column]
    lowered_column = column.lower()
    for key, value in row.items():
        if str(key).split(".")[-1].lower() == lowered_column:
            return value
    return None


def _create_sqlite_rowset_table(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    normalized_columns: list[str] = []
    for column in columns or _columns_for(rows):
        column_name = str(column).split(".")[-1]
        if SAFE_TABLE_RE.match(column_name) and column_name not in normalized_columns:
            normalized_columns.append(column_name)
    if not normalized_columns:
        normalized_columns = ["_empty"]
    definitions = [
        f"{_sqlite_quote_identifier(column)} {_sql_type_for([_sql_row_value(row, column) for row in rows])}"
        for column in normalized_columns
    ]
    conn.execute(f"CREATE TEMP TABLE {_sqlite_quote_identifier(table_name)} ({', '.join(definitions)})")
    if rows:
        columns_sql = ", ".join(_sqlite_quote_identifier(column) for column in normalized_columns)
        values_sql = ", ".join("?" for _ in normalized_columns)
        conn.executemany(
            f"INSERT INTO {_sqlite_quote_identifier(table_name)} ({columns_sql}) VALUES ({values_sql})",
            [
                tuple(_safe_sqlite_value(_sql_row_value(row, column)) for column in normalized_columns)
                for row in rows
            ],
        )


def _table_name_for_parent(parent_id: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", parent_id).strip("_")
    if not normalized or normalized[0].isdigit():
        normalized = f"node_{normalized or index}"
    return f"input_{normalized}"


def _execute_sql_in_memory(
    parent_ids: list[str],
    rowsets_by_node: dict[str, list[dict[str, Any]]],
    columns_by_node: dict[str, list[str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    sql = _assert_select_sql(str(config.get("sql") or ""))
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        for index, parent_id in enumerate(parent_ids):
            rows = [dict(row) for row in rowsets_by_node.get(parent_id, [])]
            columns = columns_by_node.get(parent_id, []) or _columns_for(rows)
            table_names = [_table_name_for_parent(parent_id, index + 1), f"input_{index + 1}"]
            if index == 0:
                table_names.insert(0, "input")
            created: set[str] = set()
            for table_name in table_names:
                if table_name in created:
                    continue
                _create_sqlite_rowset_table(conn, table_name, columns, rows)
                created.add(table_name)
        cursor = conn.execute(sql)
        columns = [description[0] for description in cursor.description or []]
        rows = [dict(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    finally:
        conn.close()


def _execute_sql_pushdown(
    datasource: DataSource,
    config: dict[str, Any],
    *,
    limit: int | None,
    persist: bool,
) -> dict[str, Any]:
    sql = _assert_select_sql(str(config.get("sql") or ""))
    target_table = str(config.get("target_table") or "").strip()
    mode = str(config.get("mode") or "replace").strip().lower()
    preview_limit = max(1, int(limit or 100))
    engine = get_datasource_engine(datasource.database_url)
    target_identifier = _quote_identifier(engine, target_table) if target_table else ""
    with engine.begin() as conn:
        row_count = int(conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) AS _pipeline_sql")).scalar() or 0)
        result = conn.execute(text(f"SELECT * FROM ({sql}) AS _pipeline_sql LIMIT :limit"), {"limit": preview_limit})
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]
        records_written = 0
        if persist and target_identifier:
            if mode != "append":
                conn.execute(text(f"DROP TABLE IF EXISTS {target_identifier}"))
                conn.execute(text(f"CREATE TABLE {target_identifier} AS SELECT * FROM ({sql}) AS _pipeline_sql"))
            else:
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS {target_identifier} AS SELECT * FROM ({sql}) AS _pipeline_sql WHERE 1 = 0"))
                conn.execute(text(f"INSERT INTO {target_identifier} SELECT * FROM ({sql}) AS _pipeline_sql"))
            records_written = row_count
    return {
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "records_written": records_written,
        "external_target": target_table or None,
        "execution_mode": "pushdown",
    }


def _write_target_table(datasource: DataSource, table_name: str, columns: list[str], rows: list[dict[str, Any]], mode: str) -> int:
    if not table_name or mode == "dataset_refresh":
        return len(rows)
    engine = get_datasource_engine(datasource.database_url)
    table_identifier = _quote_identifier(engine, table_name)
    normalized_columns = [column for column in columns if SAFE_TABLE_RE.match(column)]
    if not normalized_columns:
        return 0
    definitions = [
        f"{_quote_identifier(engine, column)} {_sql_type_for([row.get(column) for row in rows])}"
        for column in normalized_columns
    ]
    prepared_rows = [{column: row.get(column) for column in normalized_columns} for row in rows]
    with engine.begin() as conn:
        if mode != "append":
            conn.execute(text(f"DROP TABLE IF EXISTS {table_identifier}"))
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_identifier} ({', '.join(definitions)})"))
        if prepared_rows:
            columns_sql = ", ".join(_quote_identifier(engine, column) for column in normalized_columns)
            values_sql = ", ".join(f":{column}" for column in normalized_columns)
            conn.execute(text(f"INSERT INTO {table_identifier} ({columns_sql}) VALUES ({values_sql})"), prepared_rows)
    return len(prepared_rows)


def execute_pipeline_dag(
    pipeline: DataPipeline,
    dataset: Dataset,
    datasource: DataSource,
    payload: PipelineRunRequest,
    *,
    extractor: DatasetExtractor,
    dataset_resolver: DatasetResolver | None = None,
    datasource_resolver: DatasourceResolver | None = None,
    metadata_extractor: MetadataExtractor | None = None,
    quality_rules: list[DataQualityRule] | None = None,
    quality_evaluator: QualityEvaluator | None = None,
    now: datetime | None = None,
    until_node_id: str | None = None,
    limit: int | None = None,
    persist_load: bool = True,
) -> EtlExecutionResult:
    dag = pipeline.dag_json or {}
    upstream = _upstream_node_ids(dag)
    rowsets_by_node: dict[str, list[dict[str, Any]]] = {}
    columns_by_node: dict[str, list[str]] = {}
    final_node_id: str | None = None
    final_rows: list[dict[str, Any]] = []
    final_columns: list[str] = []
    quality_results: list[dict[str, Any]] = []
    node_logs: list[dict[str, Any]] = []
    records_read = 0
    records_written = 0
    quality_blocked = False
    run_now = now or datetime.utcnow()
    metadata_extractor = metadata_extractor or _default_metadata_extract

    for node in _topological_nodes(dag):
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "transform")
        config = _node_config(node)
        started = time.perf_counter()
        input_rows = _node_input_rows(node_id, upstream, rowsets_by_node)
        input_columns = _node_input_columns(node_id, upstream, columns_by_node)
        rows = input_rows
        columns = input_columns
        rows_in = len(input_rows)
        node_records_read = rows_in
        status = "success"
        errors: list[str] = []
        execution_mode: str | None = None
        external_target: str | None = None
        if node_type not in SUPPORTED_NODE_TYPES:
            status = "skipped"
            errors.append("unsupported node type")
        elif quality_blocked and node_type in {"load", "sink", "reverse_etl"}:
            status = "skipped"
            node_records_written = 0
        else:
            try:
                if node_type in {"source", "extract"}:
                    source_dataset = dataset
                    source_datasource = datasource
                    if config.get("dataset_id") and dataset_resolver:
                        source_dataset, source_datasource = dataset_resolver(int(config["dataset_id"]))
                    extract = extractor(source_dataset, source_datasource)
                    rows = [dict(row) for row in extract.get("rows", [])]
                    rows = _filter_incremental_rows(rows, config, payload, source_dataset)
                    columns = _columns_for(rows, extract.get("columns", []))
                    records_read += len(rows)
                    node_records_read = len(rows)
                    if persist_load and not payload.dry_run:
                        _update_incremental_watermark(source_dataset, rows, config)
                elif node_type == "metadata_extract":
                    source_datasource = datasource
                    if config.get("datasource_id") and datasource_resolver:
                        source_datasource = datasource_resolver(int(config["datasource_id"]))
                    extract = metadata_extractor(source_datasource, config)
                    rows = [dict(row) for row in extract.get("rows", [])]
                    columns = _columns_for(rows, extract.get("columns", []))
                    records_read += len(rows)
                    node_records_read = len(rows)
                elif node_type == "transform":
                    rows = _execute_transform(input_rows, config)
                    columns = _columns_for(rows, columns)
                elif node_type == "union":
                    parent_ids = upstream.get(node_id) or []
                    rows = _execute_union([rowsets_by_node.get(parent_id, []) for parent_id in parent_ids], config)
                    parent_columns = [column for parent_id in parent_ids for column in columns_by_node.get(parent_id, [])]
                    columns = _columns_for(rows, parent_columns)
                elif node_type == "join":
                    parent_ids = upstream.get(node_id) or []
                    left_id = str(config.get("left_node_id") or (parent_ids[0] if parent_ids else "")).strip()
                    right_id = str(config.get("right_node_id") or (parent_ids[1] if len(parent_ids) > 1 else "")).strip()
                    if not left_id or not right_id:
                        raise ValueError("join node requires two upstream nodes")
                    rows = _execute_join(rowsets_by_node.get(left_id, []), rowsets_by_node.get(right_id, []), config)
                    columns = _columns_for(rows, columns_by_node.get(left_id, []) + columns_by_node.get(right_id, []))
                elif node_type == "sql":
                    parent_ids = upstream.get(node_id) or []
                    execution_mode = str(config.get("execution_mode") or ("pushdown" if not parent_ids else "in_memory")).lower()
                    if execution_mode == "pushdown":
                        source_datasource = datasource
                        if config.get("datasource_id") and datasource_resolver:
                            source_datasource = datasource_resolver(int(config["datasource_id"]))
                        sql_result = _execute_sql_pushdown(
                            source_datasource,
                            config,
                            limit=limit,
                            persist=persist_load and not payload.dry_run,
                        )
                        rows = [dict(row) for row in sql_result.get("rows", [])]
                        columns = _columns_for(rows, sql_result.get("columns", []))
                        node_records_read = int(sql_result.get("row_count") or len(rows))
                        records_read += node_records_read
                        node_records_written = int(sql_result.get("records_written") or 0)
                        records_written += node_records_written
                        external_target = sql_result.get("external_target")
                    else:
                        sql_result = _execute_sql_in_memory(parent_ids, rowsets_by_node, columns_by_node, config)
                        rows = [dict(row) for row in sql_result.get("rows", [])]
                        columns = _columns_for(rows, sql_result.get("columns", []))
                        node_records_read = sum(len(rowsets_by_node.get(parent_id, [])) for parent_id in parent_ids)
                        records_read += node_records_read
                        execution_mode = "in_memory"
                elif node_type == "quality":
                    if quality_evaluator:
                        node_quality_results = quality_evaluator(quality_rules or [], input_rows, datasource, run_now)
                        quality_results.extend(node_quality_results)
                    else:
                        node_quality_results = []
                    quality_failed = any(result.get("status") == "failed" for result in node_quality_results)
                    quality_warning = any(result.get("status") == "warning" for result in node_quality_results)
                    if quality_failed:
                        status = "failed"
                        quality_blocked = True
                    elif quality_warning:
                        status = "warning"
                    rows = input_rows
                    columns = input_columns
                elif node_type in {"load", "sink"}:
                    rows = input_rows
                    columns = input_columns
                    if payload.dry_run or not persist_load:
                        node_records_written = 0
                    else:
                        node_records_written = _write_target_table(
                            datasource,
                            str(config.get("target_table") or "").strip(),
                            _columns_for(rows, columns),
                            rows,
                            str(config.get("mode") or "replace").strip(),
                        )
                        records_written += node_records_written
                elif node_type == "reverse_etl":
                    rows = input_rows
                    columns = input_columns
                    target_type = str(config.get("target_type") or "database").lower()
                    if target_type != "database":
                        raise ValueError(f"unsupported reverse_etl target_type: {target_type}")
                    target_datasource = datasource
                    if config.get("datasource_id") and datasource_resolver:
                        target_datasource = datasource_resolver(int(config["datasource_id"]))
                    external_target = str(config.get("target_table") or "").strip()
                    execution_mode = "reverse_etl"
                    if payload.dry_run or not persist_load:
                        node_records_written = 0
                    else:
                        node_records_written = _write_target_table(
                            target_datasource,
                            external_target,
                            _columns_for(rows, columns),
                            rows,
                            str(config.get("mode") or "append").strip(),
                        )
                        records_written += node_records_written
            except Exception as exc:
                status = "failed"
                errors.append(str(exc))
                if node_type in {"source", "extract", "metadata_extract", "transform", "join", "union", "sql", "quality", "reverse_etl"}:
                    quality_blocked = True

        rowsets_by_node[node_id] = [dict(row) for row in rows]
        columns_by_node[node_id] = _columns_for(rows, columns)
        final_node_id = node_id
        final_rows = rowsets_by_node[node_id]
        final_columns = columns_by_node[node_id]
        duration_ms = int((time.perf_counter() - started) * 1000)
        node_logs.append(
            {
                "node_id": node_id,
                "label": node.get("label") or node_id,
                "type": node_type,
                "status": status,
                "rows_in": rows_in,
                "rows_out": len(rows),
                "records_read": node_records_read,
                "records_written": node_records_written if node_type in {"load", "sink", "sql", "reverse_etl"} and "node_records_written" in locals() else len(rows),
                "records_failed": sum(result.get("failed_count", 0) for result in quality_results if result.get("status") == "failed") if node_type == "quality" else 0,
                "duration_ms": duration_ms,
                "preview": _preview_rows(rows),
                "errors": errors,
                "quality_results": node_quality_results if node_type == "quality" and "node_quality_results" in locals() else [],
                **({"execution_mode": execution_mode} if execution_mode else {}),
                **({"external_target": external_target} if external_target else {}),
            }
        )
        if "node_records_written" in locals():
            del node_records_written
        if "node_quality_results" in locals():
            del node_quality_results
        if until_node_id and node_id == until_node_id:
            break

    records_failed = sum(result.get("failed_count", 0) for result in quality_results if result.get("status") == "failed")
    failed_nodes = [node for node in node_logs if node["status"] == "failed"]
    status = "failed" if failed_nodes else "success"
    error_message = None
    if failed_nodes:
        messages = [error for node in failed_nodes for error in node.get("errors", [])]
        if not messages:
            messages = [
                f"{result.get('name')}: {result.get('message')}"
                for result in quality_results
                if result.get("status") == "failed"
            ]
        error_message = "；".join(message for message in messages if message) or "管道执行失败"
    if records_written == 0 and not payload.dry_run and not quality_blocked and not until_node_id:
        has_load = any((node.get("type") in {"load", "sink", "reverse_etl"} or (node.get("type") == "sql" and (_node_config(node).get("target_table")))) for node in dag.get("nodes", []) if isinstance(node, dict))
        if not has_load:
            records_written = len(final_rows)

    return EtlExecutionResult(
        status=status,
        columns=_columns_for(final_rows, final_columns),
        rows=final_rows[: max(1, int(limit))] if limit else final_rows,
        node_logs={
            "summary": {
                "node_count": len(dag.get("nodes", []) or []),
                "edge_count": len(dag.get("edges", []) or []),
                "source_row_count": records_read,
                "final_node_id": final_node_id,
                "final_row_count": len(final_rows),
                "final_columns": _columns_for(final_rows, final_columns),
                "node_row_counts": {node_id: len(rowset) for node_id, rowset in rowsets_by_node.items()},
                "quality": "failed" if quality_blocked else "passed" if quality_results else "not_checked",
                "quality_results": quality_results,
                "dry_run": payload.dry_run,
                "run_window": {
                    "start": payload.window_start.isoformat() if payload.window_start else None,
                    "end": payload.window_end.isoformat() if payload.window_end else None,
                },
                "retry_count": int(getattr(pipeline, "retry_count", None) or 2),
                "timeout_minutes": int(getattr(pipeline, "timeout_minutes", None) or 60),
            },
            "nodes": node_logs,
        },
        records_read=records_read,
        records_written=records_written,
        records_failed=records_failed,
        error_message=error_message,
    )
