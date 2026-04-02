"""Excel query executor using DuckDB."""
import os
import re
import duckdb
import pandas as pd
from typing import Dict, Any, List
from app.core.excel_uploads import resolve_excel_source_path

# Sheet name to table name mapping for ChatBI数据.xlsx
SHEET_TABLE_MAP = {
    "IP_PA_MAINRECORD-班次主数据": "mainrecord",
    "IP_PA_NGTYPE-失效详情": "ngtype",
    "IP_PA_PRODUCTION-各型号产出": "production",
    "IP_PA_PRODUCTION_OK-各型号详细信息": "production_ok",
    "IP_PA_RTYINFO-各工站投入产出详情": "rtyinfo",
}

SAMPLE_VALUE_COLUMNS = ("LINE", "NGTYPE", "STN", "PARTNO", "OP", "SHIFTNAME")
MAX_SAMPLE_VALUES = 5


def _normalize_table_name(sheet_name: str) -> str:
    """Convert sheet name to valid SQL table name."""
    if sheet_name in SHEET_TABLE_MAP:
        return SHEET_TABLE_MAP[sheet_name]
    # Fallback: lowercase, replace special chars
    name = sheet_name.split("-")[0].lower()
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def _sqlite_modifier_to_interval(modifier: str) -> str | None:
    match = re.fullmatch(r"([+-])\s*(\d+)\s+(day|days|month|months|year|years)", modifier.strip(), re.I)
    if not match:
        return None
    sign, amount, unit = match.groups()
    normalized_unit = unit.lower()
    if normalized_unit.endswith("s"):
        normalized_unit = normalized_unit[:-1]
    operator = "+" if sign == "+" else "-"
    return f"{operator} INTERVAL '{amount} {normalized_unit}'"


def rewrite_excel_sql_for_duckdb(sql: str) -> str:
    def replace_now(match: re.Match[str]) -> str:
        modifier = match.group("modifier")
        if not modifier:
            return "CURRENT_DATE"
        interval = _sqlite_modifier_to_interval(modifier)
        if not interval:
            return match.group(0)
        return f"CURRENT_DATE {interval}"

    def replace_expr(match: re.Match[str]) -> str:
        expr = match.group("expr").strip()
        modifier = match.group("modifier")
        if not modifier:
            return f"DATE({expr})"
        interval = _sqlite_modifier_to_interval(modifier)
        if not interval:
            return match.group(0)
        return f"CAST({expr} AS DATE) {interval}"

    sql = re.sub(
        r"DATE\s*\(\s*'now'\s*(?:,\s*'(?P<modifier>[^']+)')?\s*\)",
        replace_now,
        sql,
        flags=re.I,
    )
    sql = re.sub(
        r"DATE\s*\(\s*(?P<expr>(?!'now')[^,\)]+?)\s*(?:,\s*'(?P<modifier>[^']+)')?\s*\)",
        replace_expr,
        sql,
        flags=re.I,
    )
    return sql


def execute_excel_query(file_path: str, sql: str) -> Dict[str, Any]:
    """Execute SQL query against Excel file using DuckDB.
    
    Args:
        file_path: Path to Excel file
        sql: SQL query to execute
        
    Returns:
        Dict with 'columns' (list of column names) and 'rows' (list of dicts)
    """
    # Load all sheets into DataFrames
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    dfs = {}
    for sheet_name in xlsx.sheet_names:
        table_name = _normalize_table_name(sheet_name)
        dfs[table_name] = pd.read_excel(xlsx, sheet_name=sheet_name)
    
    # Create DuckDB connection and register DataFrames
    conn = duckdb.connect(":memory:")
    for table_name, df in dfs.items():
        conn.register(table_name, df)
    
    # Execute SQL
    sql = rewrite_excel_sql_for_duckdb(sql)
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    
    conn.close()
    return {"columns": columns, "rows": rows}


def generate_excel_metadata(file_path: str) -> str:
    """Generate metadata_prompt from Excel structure.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Metadata string describing all tables and columns
    """
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    lines = ["数据库表结构信息："]
    
    for sheet_name in xlsx.sheet_names:
        table_name = _normalize_table_name(sheet_name)
        df = pd.read_excel(xlsx, sheet_name=sheet_name)
        cols = ", ".join(str(c) for c in df.columns[:10])
        if len(df.columns) > 10:
            cols += f"... (共{len(df.columns)}列)"
        # Extract Chinese description from sheet name
        desc = sheet_name.split("-")[-1] if "-" in sheet_name else sheet_name
        lines.append(f"- {table_name} 表 ({desc}): {cols}")
        sample_lines = []
        for column in SAMPLE_VALUE_COLUMNS:
            if column not in df.columns:
                continue
            values = []
            for value in df[column].dropna().tolist():
                text = str(value).strip()
                if not text or text in values:
                    continue
                values.append(text)
                if len(values) >= MAX_SAMPLE_VALUES:
                    break
            if values:
                sample_lines.append(f"  - {column} 示例值: {', '.join(values)}")
        if sample_lines:
            lines.extend(sample_lines)

    lines.append("重要提示：当用户问题中的业务名称与某列示例值完整匹配时，优先直接使用该列做精确过滤，不要把一个完整名称拆成多个字段条件。")

    return "\n".join(lines)


def get_excel_tables(file_path: str) -> List[str]:
    """Get list of available table names from Excel file."""
    resolved_path = resolve_excel_source_path(file_path)
    xlsx = pd.ExcelFile(resolved_path)
    return [_normalize_table_name(s) for s in xlsx.sheet_names]


def test_excel_connection(file_path: str) -> Dict[str, str]:
    """Test if Excel file is accessible.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Dict with 'status' ('ok' or 'error') and 'message'
    """
    resolved_path = resolve_excel_source_path(file_path)
    if not os.path.isfile(resolved_path):
        return {"status": "error", "message": f"文件不存在: {file_path}"}
    try:
        xlsx = pd.ExcelFile(resolved_path)
        tables = get_excel_tables(resolved_path)
        return {
            "status": "ok",
            "message": f"文件可读，包含 {len(xlsx.sheet_names)} 个表: {', '.join(tables)}"
        }
    except Exception as e:
        return {"status": "error", "message": f"文件读取失败: {e}"}
