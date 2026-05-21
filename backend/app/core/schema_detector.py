"""Schema detection and prompt generation utilities."""
import pandas as pd
import re
from sqlalchemy import create_engine, inspect, text
from typing import Dict, Any, List

from app.schemas.datasource import SchemaMetadata, TableSchema, ColumnSchema, RelationshipSchema
from app.core.excel_uploads import resolve_excel_source_path


MAX_RELATIONSHIP_PROBE_VALUES = 200
MAX_INFERRED_RELATIONSHIPS = 80


# Sheet name to table name mapping
SHEET_TABLE_MAP = {
    "IP_PA_MAINRECORD-班次主数据": ("mainrecord", "班次主数据"),
    "IP_PA_NGTYPE-失效详情": ("ngtype", "失效详情"),
    "IP_PA_PRODUCTION-各型号产出": ("production", "各型号产出"),
    "IP_PA_PRODUCTION_OK-各型号详细信息": ("production_ok", "各型号详细信息"),
    "IP_PA_RTYINFO-各工站投入产出详情": ("rtyinfo", "各工站投入产出详情"),
}


def _normalize_table_name(sheet_name: str) -> tuple:
    """Convert sheet name to (table_name, description)."""
    if sheet_name in SHEET_TABLE_MAP:
        return SHEET_TABLE_MAP[sheet_name]
    # Fallback
    name = sheet_name.split("-")[0].lower()
    name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    desc = sheet_name.split("-")[-1] if "-" in sheet_name else sheet_name
    return (name, desc)


def _infer_dtype(series: pd.Series) -> str:
    """Infer SQL-like type from pandas series."""
    dtype = series.dtype
    if pd.api.types.is_integer_dtype(dtype):
        return "INTEGER"
    elif pd.api.types.is_float_dtype(dtype):
        return "FLOAT"
    elif pd.api.types.is_bool_dtype(dtype):
        return "BOOLEAN"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "DATETIME"
    else:
        return "VARCHAR"


def detect_excel_schema(file_path: str) -> SchemaMetadata:
    """Detect schema from Excel file."""
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    tables = []
    
    for sheet_name in xlsx.sheet_names:
        table_name, description = _normalize_table_name(sheet_name)
        df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=100)  # Sample for type inference
        
        columns = []
        for col in df.columns:
            col_type = _infer_dtype(df[col])
            columns.append(ColumnSchema(
                name=str(col),
                type=col_type,
                description=None  # User can fill this in
            ))
        
        tables.append(TableSchema(
            name=table_name,
            description=description,
            columns=columns
        ))
    
    # Auto-detect relationships based on common ID patterns
    relationships = _detect_relationships(tables)
    
    return SchemaMetadata(tables=tables, relationships=relationships)


def _detect_relationships(tables: List[TableSchema]) -> List[RelationshipSchema]:
    """Auto-detect relationships based on column naming patterns."""
    relationships = []
    table_names = {t.name for t in tables}
    table_columns = {t.name: {c.name for c in t.columns} for t in tables}
    
    for table in tables:
        for col in table.columns:
            col_upper = col.name.upper()
            # Check for MAINID -> mainrecord.ID pattern
            if col_upper == "MAINID" and "mainrecord" in table_names:
                if "ID" in table_columns.get("mainrecord", set()):
                    relationships.append(RelationshipSchema(
                        from_table=table.name,
                        from_column=col.name,
                        to_table="mainrecord",
                        to_column="ID",
                        status="inferred",
                        confidence=0.78,
                        source="name_match",
                        evidence=["命名匹配：MAINID 通常关联 mainrecord.ID"],
                    ))
            # Generic pattern: XXXID -> xxx.ID
            elif col_upper.endswith("ID") and col_upper != "ID":
                ref_table = col_upper[:-2].lower()
                if ref_table in table_names and "ID" in table_columns.get(ref_table, set()):
                    relationships.append(RelationshipSchema(
                        from_table=table.name,
                        from_column=col.name,
                        to_table=ref_table,
                        to_column="ID",
                        status="inferred",
                        confidence=0.72,
                        source="name_match",
                        evidence=[f"命名匹配：{col.name} 指向 {ref_table}.ID"],
                    ))
    
    return relationships


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _singular_aliases(table_name: str) -> set[str]:
    normalized = _normalize_identifier(table_name)
    aliases = {normalized}
    if normalized.endswith("ies") and len(normalized) > 3:
        aliases.add(f"{normalized[:-3]}y")
    if normalized.endswith("s") and len(normalized) > 3:
        aliases.add(normalized[:-1])
    return {item for item in aliases if item}


def _column_reference_base(column_name: str) -> str:
    lowered = str(column_name or "").lower().strip()
    for suffix in ("_id", "id"):
        if lowered.endswith(suffix) and len(lowered) > len(suffix):
            return _normalize_identifier(lowered[: -len(suffix)])
    return ""


def _relationship_key(rel: RelationshipSchema) -> tuple[str, str, str, str]:
    return (
        rel.from_table.lower(),
        rel.from_column.lower(),
        rel.to_table.lower(),
        rel.to_column.lower(),
    )


def _quote_name(engine, name: str) -> str:
    preparer = engine.dialect.identifier_preparer
    return ".".join(preparer.quote(part) for part in name.split("."))


def _limited_distinct_sql(engine, table: str, column: str, limit: int) -> str:
    quoted_table = _quote_name(engine, table)
    quoted_column = _quote_name(engine, column)
    dialect = str(getattr(engine.dialect, "name", "") or "").lower()
    if dialect == "mssql":
        return (
            f"SELECT DISTINCT TOP {limit} {quoted_column} AS value "
            f"FROM {quoted_table} WHERE {quoted_column} IS NOT NULL"
        )
    if dialect == "oracle":
        return (
            f"SELECT DISTINCT {quoted_column} AS value FROM {quoted_table} "
            f"WHERE {quoted_column} IS NOT NULL FETCH FIRST {limit} ROWS ONLY"
        )
    return (
        f"SELECT DISTINCT {quoted_column} AS value FROM {quoted_table} "
        f"WHERE {quoted_column} IS NOT NULL LIMIT {limit}"
    )


def _probe_relationship_evidence(
    engine,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> tuple[float | None, float | None, list[str]]:
    evidence: list[str] = []
    try:
        with engine.connect() as conn:
            child_values = [
                row[0]
                for row in conn.execute(
                    text(_limited_distinct_sql(engine, from_table, from_column, MAX_RELATIONSHIP_PROBE_VALUES))
                ).fetchall()
                if row[0] is not None
            ]
            if not child_values:
                return None, None, ["子表关联字段样例为空，未做值覆盖率验证"]

            params = {f"v{i}": value for i, value in enumerate(child_values)}
            placeholders = ", ".join(f":v{i}" for i in range(len(child_values)))
            parent_table = _quote_name(engine, to_table)
            parent_column = _quote_name(engine, to_column)
            match_count = conn.execute(
                text(
                    f"SELECT COUNT(DISTINCT {parent_column}) "
                    f"FROM {parent_table} WHERE {parent_column} IN ({placeholders})"
                ),
                params,
            ).scalar() or 0
            coverage = min(1.0, float(match_count) / max(1, len(child_values)))
            evidence.append(f"值覆盖率 {coverage:.1%}")

            unique_row = conn.execute(
                text(
                    f"SELECT COUNT(*) AS total_count, COUNT(DISTINCT {parent_column}) AS distinct_count "
                    f"FROM {parent_table} WHERE {parent_column} IS NOT NULL"
                )
            ).first()
            total_count = int(unique_row[0] or 0) if unique_row else 0
            distinct_count = int(unique_row[1] or 0) if unique_row else 0
            unique_ratio = float(distinct_count) / total_count if total_count else None
            if unique_ratio is not None:
                evidence.append(f"父表字段唯一性 {unique_ratio:.1%}")
            return coverage, unique_ratio, evidence
    except Exception as exc:
        return None, None, [f"值验证跳过：{exc.__class__.__name__}"]


def _candidate_parent_columns(inspector, table: TableSchema) -> list[str]:
    columns = [column.name for column in table.columns]
    normalized_columns = {_normalize_identifier(column): column for column in columns}
    candidates: list[str] = []
    try:
        pk_columns = inspector.get_pk_constraint(table.name).get("constrained_columns") or []
    except Exception:
        pk_columns = []
    for column in pk_columns:
        if column in columns and column not in candidates:
            candidates.append(column)

    aliases = _singular_aliases(table.name)
    for key in ("id", *[f"{alias}id" for alias in aliases]):
        column = normalized_columns.get(key)
        if column and column not in candidates:
            candidates.append(column)
    return candidates


def _infer_database_relationships(engine, inspector, tables: list[TableSchema], existing: list[RelationshipSchema]) -> list[RelationshipSchema]:
    inferred: list[RelationshipSchema] = []
    existing_keys = {_relationship_key(rel) for rel in existing}
    parent_columns_by_table = {table.name: _candidate_parent_columns(inspector, table) for table in tables}

    for child_table in tables:
        for child_column in child_table.columns:
            ref_base = _column_reference_base(child_column.name)
            if not ref_base or ref_base in {"i", "d"}:
                continue
            for parent_table in tables:
                if parent_table.name == child_table.name:
                    continue
                parent_aliases = _singular_aliases(parent_table.name)
                if ref_base not in parent_aliases and not any(alias.startswith(ref_base) for alias in parent_aliases):
                    continue
                for parent_column in parent_columns_by_table.get(parent_table.name, []):
                    relationship = RelationshipSchema(
                        from_table=child_table.name,
                        from_column=child_column.name,
                        to_table=parent_table.name,
                        to_column=parent_column,
                        status="inferred",
                        confidence=0.72,
                        source="name_match",
                        evidence=[
                            f"命名匹配：{child_table.name}.{child_column.name} 指向 {parent_table.name}.{parent_column}"
                        ],
                    )
                    if _relationship_key(relationship) in existing_keys:
                        continue
                    coverage, unique_ratio, value_evidence = _probe_relationship_evidence(
                        engine,
                        child_table.name,
                        child_column.name,
                        parent_table.name,
                        parent_column,
                    )
                    relationship.evidence.extend(value_evidence)
                    if coverage is not None:
                        if coverage < 0.6:
                            continue
                        unique_bonus = 0.1 if unique_ratio is not None and unique_ratio >= 0.95 else 0
                        relationship.confidence = round(min(0.98, 0.55 + coverage * 0.35 + unique_bonus), 2)
                        relationship.source = "name_and_value_probe"
                    inferred.append(relationship)
                    existing_keys.add(_relationship_key(relationship))
                    if len(inferred) >= MAX_INFERRED_RELATIONSHIPS:
                        return inferred
    return inferred


def detect_database_schema(database_url: str) -> SchemaMetadata:
    """Detect schema from database using SQLAlchemy inspection."""
    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = []
    
    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            col_type = str(col["type"]).split("(")[0]  # Remove length info
            columns.append(ColumnSchema(
                name=col["name"],
                type=col_type,
                description=col.get("comment")
            ))
        
        tables.append(TableSchema(
            name=table_name,
            description=None,
            columns=columns
        ))
    
    # Detect foreign key relationships
    relationships = []
    for table_name in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table_name):
            if fk["constrained_columns"] and fk["referred_columns"]:
                relationships.append(RelationshipSchema(
                    from_table=table_name,
                    from_column=fk["constrained_columns"][0],
                    to_table=fk["referred_table"],
                    to_column=fk["referred_columns"][0],
                    status="confirmed",
                    confidence=1.0,
                    source="foreign_key",
                    evidence=["数据库显式外键"],
                ))
    relationships.extend(_infer_database_relationships(engine, inspector, tables, relationships))
    
    engine.dispose()
    return SchemaMetadata(tables=tables, relationships=relationships)


def detect_schema(source_path: str, source_type: str) -> SchemaMetadata:
    """Detect schema from datasource based on type."""
    if source_type == "excel":
        return detect_excel_schema(source_path)
    else:
        return detect_database_schema(source_path)


def schema_to_prompt(schema: SchemaMetadata) -> str:
    """Generate LLM-friendly metadata prompt from schema."""
    lines = ["数据库表结构信息："]
    
    for table in schema.tables:
        desc = f" ({table.description})" if table.description else ""
        lines.append(f"\n### {table.name} 表{desc}")
        
        if table.columns:
            lines.append("| 列名 | 类型 | 说明 |")
            lines.append("|------|------|------|")
            for col in table.columns:
                col_desc = col.description or ""
                lines.append(f"| {col.name} | {col.type} | {col_desc} |")
    
    if schema.relationships:
        lines.append("\n### 表关联关系")
        for rel in schema.relationships:
            meta = []
            if rel.status:
                meta.append(rel.status)
            if rel.confidence is not None:
                meta.append(f"置信度 {rel.confidence:.2f}")
            if rel.evidence:
                meta.append("证据：" + "；".join(rel.evidence[:3]))
            suffix = f"（{'；'.join(meta)}）" if meta else ""
            lines.append(f"- {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}{suffix}")
    
    return "\n".join(lines)
