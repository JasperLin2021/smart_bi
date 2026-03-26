# Excel Data Source Support

## Overview

Add Excel file support to the existing multi-datasource system. Users can configure Excel files as data sources and query them using natural language, with the LLM generating SQL that executes against the Excel data via DuckDB.

## Target File

`/home/qqr/smart_bi/ChatBI数据.xlsx` - Manufacturing production data with 5 sheets.

## Architecture

```
User Query → LLM generates SQL → Query Executor Router →
  ├─ source_type='database' → SQLAlchemy engine (existing)
  └─ source_type='excel' → DuckDB + pandas DataFrames (new)
```

## Design Decisions

1. **Query Method**: DuckDB SQL - keeps existing text2sql flow, LLM generates standard SQL
2. **Source Type Identification**: Add `source_type` field to DataSource model
3. **Sheet Handling**: All sheets become queryable tables with normalized names

## Implementation Details

### 1. Database Schema Changes

**File**: `backend/app/models/datasource.py`

Add column:
```python
source_type = Column(String(32), default="database")  # "database" | "excel"
```

For Excel sources:
- `database_url` stores the file path (e.g., `/home/qqr/smart_bi/ChatBI数据.xlsx`)
- `metadata_prompt` auto-generated from sheet structure

### 2. Pydantic Schema Changes

**File**: `backend/app/schemas/datasource.py`

Add `source_type` field to:
- `DataSourceCreate` (optional, defaults to "database")
- `DataSourceUpdate` (optional)
- `DataSourceOut` (required)

### 3. New Excel Query Executor

**File**: `backend/app/core/excel_executor.py` (new)

```python
import duckdb
import pandas as pd
from typing import Dict, Any

# Sheet name to table name mapping
SHEET_TABLE_MAP = {
    "IP_PA_MAINRECORD-班次主数据": "mainrecord",
    "IP_PA_NGTYPE-失效详情": "ngtype", 
    "IP_PA_PRODUCTION-各型号产出": "production",
    "IP_PA_PRODUCTION_OK-各型号详细信息": "production_ok",
    "IP_PA_RTYINFO-各工站投入产出详情": "rtyinfo",
}

def execute_excel_query(file_path: str, sql: str) -> Dict[str, Any]:
    """Execute SQL query against Excel file using DuckDB."""
    # 1. Load all sheets into DataFrames
    xlsx = pd.ExcelFile(file_path)
    dfs = {}
    for sheet_name in xlsx.sheet_names:
        table_name = SHEET_TABLE_MAP.get(sheet_name, sheet_name.lower().replace("-", "_"))
        dfs[table_name] = pd.read_excel(xlsx, sheet_name=sheet_name)
    
    # 2. Create DuckDB connection and register DataFrames
    conn = duckdb.connect(":memory:")
    for table_name, df in dfs.items():
        conn.register(table_name, df)
    
    # 3. Execute SQL
    result = conn.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, row)) for row in result.fetchall()]
    
    conn.close()
    return {"columns": columns, "rows": rows}

def generate_excel_metadata(file_path: str) -> str:
    """Generate metadata_prompt from Excel structure."""
    xlsx = pd.ExcelFile(file_path)
    lines = ["数据库表结构信息："]
    
    for sheet_name in xlsx.sheet_names:
        table_name = SHEET_TABLE_MAP.get(sheet_name, sheet_name.lower().replace("-", "_"))
        df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=0)
        cols = ", ".join(df.columns[:10])
        if len(df.columns) > 10:
            cols += "..."
        # Extract Chinese description from sheet name
        desc = sheet_name.split("-")[-1] if "-" in sheet_name else ""
        lines.append(f"- {table_name} 表 ({desc}): {cols}")
    
    return "\n".join(lines)

def test_excel_connection(file_path: str) -> Dict[str, str]:
    """Test if Excel file is accessible."""
    import os
    if not os.path.isfile(file_path):
        return {"status": "error", "message": f"文件不存在: {file_path}"}
    try:
        pd.ExcelFile(file_path)
        return {"status": "ok", "message": "文件可读"}
    except Exception as e:
        return {"status": "error", "message": f"文件读取失败: {e}"}
```

### 4. Query Router Changes

**File**: `backend/app/api/query.py`

Modify the SQL execution section (~line 86-97):

```python
from app.core.excel_executor import execute_excel_query

# Replace existing execution block with:
if datasource.source_type == "excel":
    result = execute_excel_query(datasource.database_url, sql_query)
    rows = result["rows"]
else:
    ds_engine = get_datasource_engine(datasource.database_url)
    with ds_engine.connect() as conn:
        result_proxy = conn.execute(text(sql_query))
        columns = list(result_proxy.keys())
        rows = [dict(row._mapping) for row in result_proxy.fetchall()]
        result = {"columns": columns, "rows": rows}
```

### 5. Datasource API Changes

**File**: `backend/app/api/datasource.py`

#### Create Endpoint
- Accept `source_type` parameter
- For Excel sources: auto-generate `metadata_prompt` if not provided

#### Test Endpoint
- For Excel sources: use `test_excel_connection()` instead of SQLAlchemy

### 6. Database Migration

Add column to existing table:
```sql
ALTER TABLE datasources ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) DEFAULT 'database';
```

### 7. Dependencies

**File**: `backend/requirements.txt`

Add:
```
duckdb>=0.9.0
openpyxl>=3.1.0
```

## Excel Sheet Structure

| Table Name | Source Sheet | Description | Key Columns |
|------------|--------------|-------------|-------------|
| mainrecord | IP_PA_MAINRECORD-班次主数据 | Shift main data | ID, LINE, SHIFTID, OEE, RTY, TOTALCOUNT |
| ngtype | IP_PA_NGTYPE-失效详情 | Failure details | ID, MAINID, LINE, NGCOUNT, NGTYPE |
| production | IP_PA_PRODUCTION-各型号产出 | Model production | ID, MAINID, PARTNO, TOTALCOUNT, OKCOUNT |
| production_ok | IP_PA_PRODUCTION_OK-各型号详细信息 | Model details | ID, MAINID, CT, H00-H23, PARTNO |
| rtyinfo | IP_PA_RTYINFO-各工站投入产出详情 | Station I/O | ID, MAINID, OP, STN, TOTAL, NGCOUNT, OKCOUNT |

## Example Usage

1. Admin creates Excel datasource via UI:
   - Name: "生产数据Excel"
   - Slug: "production-excel"
   - Source Type: "excel"
   - File Path: `/home/qqr/smart_bi/ChatBI数据.xlsx`
   - Metadata: (auto-generated)

2. User asks: "各产线的OEE平均值是多少？"

3. LLM generates SQL:
   ```sql
   SELECT LINE, AVG(OEE) as avg_oee 
   FROM mainrecord 
   GROUP BY LINE
   ```

4. DuckDB executes against Excel data and returns results.

## Error Handling

- File not found: Return 404 with clear message
- Invalid Excel format: Return 400 with parsing error
- SQL execution error: Return 502 with DuckDB error message
- Sheet not found in query: DuckDB returns table-not-found error

## Testing Strategy

1. Unit test `excel_executor.py` with sample Excel file
2. Integration test datasource CRUD with source_type="excel"
3. End-to-end test: create Excel datasource → ask question → verify results
