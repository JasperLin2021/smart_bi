"""Schema detection and prompt generation utilities."""
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from typing import Dict, Any, List

from app.schemas.datasource import SchemaMetadata, TableSchema, ColumnSchema, RelationshipSchema


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
    xlsx = pd.ExcelFile(file_path)
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
                        to_column="ID"
                    ))
            # Generic pattern: XXXID -> xxx.ID
            elif col_upper.endswith("ID") and col_upper != "ID":
                ref_table = col_upper[:-2].lower()
                if ref_table in table_names and "ID" in table_columns.get(ref_table, set()):
                    relationships.append(RelationshipSchema(
                        from_table=table.name,
                        from_column=col.name,
                        to_table=ref_table,
                        to_column="ID"
                    ))
    
    return relationships


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
                    to_column=fk["referred_columns"][0]
                ))
    
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
            lines.append(f"- {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}")
    
    return "\n".join(lines)
