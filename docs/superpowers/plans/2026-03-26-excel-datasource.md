# Excel Data Source Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Excel file support to the multi-datasource system, allowing users to query Excel data using natural language via DuckDB SQL execution.

**Architecture:** Add `source_type` field to distinguish database vs Excel sources. Create new `excel_executor.py` module for DuckDB-based Excel queries. Route queries based on source type in `query.py`.

**Tech Stack:** Python, FastAPI, DuckDB, pandas, openpyxl

**Spec:** `docs/superpowers/specs/2026-03-26-excel-datasource-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/app/core/excel_executor.py` | Excel query execution via DuckDB |
| Modify | `backend/app/models/datasource.py` | Add `source_type` column |
| Modify | `backend/app/schemas/datasource.py` | Add `source_type` to schemas |
| Modify | `backend/app/api/datasource.py` | Handle Excel in create/test endpoints |
| Modify | `backend/app/api/query.py` | Route queries by source type |
| Modify | `backend/app/main.py` | Add migration for source_type column |
| Modify | `backend/requirements.txt` | Add duckdb, openpyxl dependencies |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add duckdb and openpyxl to requirements**

Add to `backend/requirements.txt`:
```
duckdb>=0.9.0
openpyxl>=3.1.0
```

- [ ] **Step 2: Install dependencies**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && pip install duckdb openpyxl
```

Expected: Successfully installed duckdb and openpyxl

- [ ] **Step 3: Verify installation**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "import duckdb; import openpyxl; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/requirements.txt && git commit -m "chore: add duckdb and openpyxl dependencies"
```

---

## Task 2: Create Excel Executor Module

**Files:**
- Create: `backend/app/core/excel_executor.py`

- [ ] **Step 1: Create excel_executor.py with all functions**

Create `backend/app/core/excel_executor.py`:
```python
"""Excel query executor using DuckDB."""
import os
import duckdb
import pandas as pd
from typing import Dict, Any, List

# Sheet name to table name mapping for ChatBI数据.xlsx
SHEET_TABLE_MAP = {
    "IP_PA_MAINRECORD-班次主数据": "mainrecord",
    "IP_PA_NGTYPE-失效详情": "ngtype",
    "IP_PA_PRODUCTION-各型号产出": "production",
    "IP_PA_PRODUCTION_OK-各型号详细信息": "production_ok",
    "IP_PA_RTYINFO-各工站投入产出详情": "rtyinfo",
}


def _normalize_table_name(sheet_name: str) -> str:
    """Convert sheet name to valid SQL table name."""
    if sheet_name in SHEET_TABLE_MAP:
        return SHEET_TABLE_MAP[sheet_name]
    # Fallback: lowercase, replace special chars
    name = sheet_name.split("-")[0].lower()
    return "".join(c if c.isalnum() or c == "_" else "_" for c in name)


def execute_excel_query(file_path: str, sql: str) -> Dict[str, Any]:
    """Execute SQL query against Excel file using DuckDB.
    
    Args:
        file_path: Path to Excel file
        sql: SQL query to execute
        
    Returns:
        Dict with 'columns' (list of column names) and 'rows' (list of dicts)
    """
    # Load all sheets into DataFrames
    xlsx = pd.ExcelFile(file_path)
    dfs = {}
    for sheet_name in xlsx.sheet_names:
        table_name = _normalize_table_name(sheet_name)
        dfs[table_name] = pd.read_excel(xlsx, sheet_name=sheet_name)
    
    # Create DuckDB connection and register DataFrames
    conn = duckdb.connect(":memory:")
    for table_name, df in dfs.items():
        conn.register(table_name, df)
    
    # Execute SQL
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
    xlsx = pd.ExcelFile(file_path)
    lines = ["数据库表结构信息："]
    
    for sheet_name in xlsx.sheet_names:
        table_name = _normalize_table_name(sheet_name)
        df = pd.read_excel(xlsx, sheet_name=sheet_name, nrows=0)
        cols = ", ".join(str(c) for c in df.columns[:10])
        if len(df.columns) > 10:
            cols += f"... (共{len(df.columns)}列)"
        # Extract Chinese description from sheet name
        desc = sheet_name.split("-")[-1] if "-" in sheet_name else sheet_name
        lines.append(f"- {table_name} 表 ({desc}): {cols}")
    
    return "\n".join(lines)


def get_excel_tables(file_path: str) -> List[str]:
    """Get list of available table names from Excel file."""
    xlsx = pd.ExcelFile(file_path)
    return [_normalize_table_name(s) for s in xlsx.sheet_names]


def test_excel_connection(file_path: str) -> Dict[str, str]:
    """Test if Excel file is accessible.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Dict with 'status' ('ok' or 'error') and 'message'
    """
    if not os.path.isfile(file_path):
        return {"status": "error", "message": f"文件不存在: {file_path}"}
    try:
        xlsx = pd.ExcelFile(file_path)
        tables = get_excel_tables(file_path)
        return {
            "status": "ok",
            "message": f"文件可读，包含 {len(xlsx.sheet_names)} 个表: {', '.join(tables)}"
        }
    except Exception as e:
        return {"status": "error", "message": f"文件读取失败: {e}"}
```

- [ ] **Step 2: Test the module manually**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "
from app.core.excel_executor import execute_excel_query, generate_excel_metadata, test_excel_connection

# Test connection
result = test_excel_connection('/home/qqr/smart_bi/ChatBI数据.xlsx')
print('Connection test:', result)

# Test metadata generation
metadata = generate_excel_metadata('/home/qqr/smart_bi/ChatBI数据.xlsx')
print('Metadata:')
print(metadata)

# Test query execution
result = execute_excel_query('/home/qqr/smart_bi/ChatBI数据.xlsx', 'SELECT LINE, AVG(OEE) as avg_oee FROM mainrecord GROUP BY LINE')
print('Query result:', result)
"
```

Expected: Connection OK, metadata printed, query results with LINE and avg_oee columns

- [ ] **Step 3: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/core/excel_executor.py && git commit -m "feat: add Excel query executor module with DuckDB"
```

---

## Task 3: Add source_type to DataSource Model

**Files:**
- Modify: `backend/app/models/datasource.py`

- [ ] **Step 1: Add source_type column to model**

In `backend/app/models/datasource.py`, add after line 11 (`database_url` column):
```python
    source_type = Column(String(32), default="database")  # "database" | "excel"
```

- [ ] **Step 2: Verify model syntax**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "from app.models.datasource import DataSource; print('Model OK')"
```

Expected: `Model OK`

- [ ] **Step 3: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/models/datasource.py && git commit -m "feat: add source_type column to DataSource model"
```

---

## Task 4: Add source_type to Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas/datasource.py`

- [ ] **Step 1: Update DataSourceCreate schema**

In `backend/app/schemas/datasource.py`, add to `DataSourceCreate` class (after `database_url` field):
```python
    source_type: Optional[str] = "database"  # "database" | "excel"
```

- [ ] **Step 2: Update DataSourceUpdate schema**

Add to `DataSourceUpdate` class:
```python
    source_type: Optional[str] = None
```

- [ ] **Step 3: Update DataSourceOut schema**

Add to `DataSourceOut` class (after `slug` field):
```python
    source_type: str
```

- [ ] **Step 4: Verify schemas**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "from app.schemas.datasource import DataSourceCreate, DataSourceUpdate, DataSourceOut; print('Schemas OK')"
```

Expected: `Schemas OK`

- [ ] **Step 5: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/schemas/datasource.py && git commit -m "feat: add source_type to datasource schemas"
```

---

## Task 5: Add Database Migration in Startup

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add migration for source_type column**

In `backend/app/main.py`, inside the `startup()` function, after the existing `ALTER TABLE` loop (around line 70), add:
```python
    # Add source_type column if missing
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE datasources ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) DEFAULT 'database'")
            )
    except Exception:
        pass
```

- [ ] **Step 2: Verify startup still works**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "from app.main import app; print('Startup OK')"
```

Expected: `Startup OK`

- [ ] **Step 3: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/main.py && git commit -m "feat: add migration for source_type column"
```

---

## Task 6: Update Datasource API for Excel Support

**Files:**
- Modify: `backend/app/api/datasource.py`

- [ ] **Step 1: Add import for excel_executor**

At top of `backend/app/api/datasource.py`, add import:
```python
from app.core.excel_executor import test_excel_connection, generate_excel_metadata
```

- [ ] **Step 2: Update create_datasource to handle Excel**

In `create_datasource` function, modify the DataSource creation (around line 48-58) to:
```python
    # Auto-generate metadata for Excel sources if not provided
    metadata_prompt = payload.metadata_prompt
    if payload.source_type == "excel" and not metadata_prompt:
        try:
            metadata_prompt = generate_excel_metadata(payload.database_url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取Excel文件: {e}")

    ds = DataSource(
        name=payload.name,
        slug=payload.slug,
        database_url=payload.database_url,
        source_type=payload.source_type or "database",
        metadata_prompt=metadata_prompt,
        metrics_prompt=payload.metrics_prompt,
        text2sql_prompt=payload.text2sql_prompt,
        recommend_questions=json.dumps(payload.recommend_questions, ensure_ascii=False)
        if payload.recommend_questions
        else None,
    )
```

- [ ] **Step 3: Update test_datasource for Excel**

Replace the `test_datasource` function (around line 116-133) with:
```python
@router.post("/{datasource_id}/test")
def test_datasource(
    datasource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_admin(current_user)
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    
    # Handle Excel sources differently
    if ds.source_type == "excel":
        return test_excel_connection(ds.database_url)
    
    # Database sources use SQLAlchemy
    try:
        test_engine = create_engine(ds.database_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        return {"status": "ok", "message": "连接成功"}
    except Exception as exc:
        return {"status": "error", "message": f"连接失败: {exc}"}
```

- [ ] **Step 4: Update _to_out helper to include source_type**

Find the `_to_out` helper function and ensure it includes `source_type` in the output.

- [ ] **Step 5: Verify API module loads**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "from app.api.datasource import router; print('API OK')"
```

Expected: `API OK`

- [ ] **Step 6: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/api/datasource.py && git commit -m "feat: update datasource API for Excel support"
```

---

## Task 7: Update Query API for Excel Execution

**Files:**
- Modify: `backend/app/api/query.py`

- [ ] **Step 1: Add import for excel_executor**

At top of `backend/app/api/query.py`, add:
```python
from app.core.excel_executor import execute_excel_query
```

- [ ] **Step 2: Update query execution logic**

In the `ask` function, replace the SQL execution block (around lines 86-97) with:
```python
    # Execute SQL based on source type
    result = {"columns": [], "rows": []}
    rows = []
    try:
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
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SQL执行失败: {exc}")
```

- [ ] **Step 3: Verify query module loads**

Run:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && python -c "from app.api.query import router; print('Query API OK')"
```

Expected: `Query API OK`

- [ ] **Step 4: Commit**

```bash
cd /home/qqr/smart_bi && git add backend/app/api/query.py && git commit -m "feat: add Excel query execution support"
```

---

## Task 8: Restart Backend and End-to-End Test

**Files:** None (verification only)

- [ ] **Step 1: Restart the backend server**

Stop any existing backend process, then:
```bash
cd /home/qqr/smart_bi/backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expected: Server starts with `Application startup complete`

- [ ] **Step 2: Test creating Excel datasource via API**

```bash
curl -X POST http://localhost:8000/api/datasources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "生产数据Excel",
    "slug": "production-excel", 
    "source_type": "excel",
    "database_url": "/home/qqr/smart_bi/ChatBI数据.xlsx",
    "metadata_prompt": ""
  }'
```

Expected: 200 OK with datasource created, metadata auto-generated

- [ ] **Step 3: Test Excel datasource connection**

```bash
curl -X POST http://localhost:8000/api/datasources/<id>/test \
  -H "Authorization: Bearer <token>"
```

Expected: `{"status": "ok", "message": "文件可读，包含 5 个表..."}`

- [ ] **Step 4: Test query against Excel datasource**

Use the frontend or API to ask: "各产线的OEE平均值"

Expected: Query executes via DuckDB, returns results with LINE and avg_oee columns

- [ ] **Step 5: Final commit**

```bash
cd /home/qqr/smart_bi && git add -A && git commit -m "feat: complete Excel datasource support"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add dependencies | requirements.txt |
| 2 | Create Excel executor | excel_executor.py |
| 3 | Update DataSource model | models/datasource.py |
| 4 | Update Pydantic schemas | schemas/datasource.py |
| 5 | Add DB migration | main.py |
| 6 | Update datasource API | api/datasource.py |
| 7 | Update query API | api/query.py |
| 8 | End-to-end test | - |
