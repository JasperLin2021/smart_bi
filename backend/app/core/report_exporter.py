from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.report_template import ReportRun, ReportTemplate

# pyproject 目前只有 openpyxl，没有 PDF/Word 渲染库，因此仅实现 excel 导出。
SUPPORTED_EXPORT_TYPES = {"excel"}
EXPORT_ROW_LIMIT = 5000

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_SHEET_NAME_ILLEGAL_RE = re.compile(r"[\\/*?\[\]:]")


def get_export_dir() -> Path:
    """解析导出文件目录（REPORT_EXPORT_DIR，默认 backend/exports），不存在则创建。"""
    raw = Path(settings.report_export_dir).expanduser()
    path = raw if raw.is_absolute() else Path(__file__).resolve().parents[2] / raw
    path.mkdir(parents=True, exist_ok=True)
    return path


def _render_text(value: Any, parameters: dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key in parameters:
            return str(parameters[key])
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, value)


def _safe_sheet_name(name: Any) -> str:
    cleaned = _SHEET_NAME_ILLEGAL_RE.sub(" ", str(name or "report")).strip() or "report"
    return cleaned[:31]


def _cell_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, datetime, date)):
        return value
    return str(value)


def build_excel_file(
    template: ReportTemplate,
    dataset: Dataset,
    columns: list[str],
    rows: list[dict[str, Any]],
    parameters: dict[str, Any],
    export_dir: Path,
    run_id: int,
) -> Path:
    """把模板 layout 单元格（支持 {{ 参数 }} 占位符）和数据集明细渲染成 xlsx。"""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _safe_sheet_name(template.name)

    sheet.cell(row=1, column=1, value=str(template.name)).font = Font(bold=True, size=14)
    sheet.cell(
        row=2,
        column=1,
        value=(
            f"版本 v{template.version} · 数据集 {dataset.name} · "
            f"导出时间 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
    )
    if parameters:
        sheet.cell(
            row=3,
            column=1,
            value="参数: " + ", ".join(f"{key}={value}" for key, value in parameters.items()),
        )

    row_cursor = 5
    layout = template.layout_json if isinstance(template.layout_json, dict) else {}
    cells = layout.get("cells") if isinstance(layout.get("cells"), list) else []
    max_layout_row = 0
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        try:
            layout_row = int(cell.get("row") or 0)
            layout_col = int(cell.get("col") or 0)
        except (TypeError, ValueError):
            continue
        if layout_row < 1 or layout_col < 1:
            continue
        sheet.cell(
            row=row_cursor + layout_row - 1,
            column=layout_col,
            value=_render_text(cell.get("value"), parameters),
        )
        max_layout_row = max(max_layout_row, layout_row)
    if max_layout_row:
        row_cursor += max_layout_row + 1

    header_font = Font(bold=True)
    for index, column in enumerate(columns, start=1):
        sheet.cell(row=row_cursor, column=index, value=str(column)).font = header_font
    for row_offset, row in enumerate(rows, start=1):
        for column_index, column in enumerate(columns, start=1):
            sheet.cell(
                row=row_cursor + row_offset,
                column=column_index,
                value=_cell_value(row.get(column)),
            )
    for column_index, column in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(column_index)].width = max(
            12, min(40, len(str(column)) + 4)
        )

    filename = f"report_run_{run_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.xlsx"
    path = export_dir / filename
    workbook.save(path)
    return path


def execute_report_export(db: Session, template: ReportTemplate, run: ReportRun) -> tuple[Path, int]:
    """同步执行导出：查询模板关联数据集并渲染 Excel，返回 (文件路径, 数据行数)。"""
    if run.export_type not in SUPPORTED_EXPORT_TYPES:
        raise ValueError(f"暂不支持 {run.export_type} 导出，当前仅支持 excel")

    # 延迟导入，避免 core 模块在加载期依赖 api 层。
    from app.api.datasets import _execute_dataset_preview

    dataset = db.query(Dataset).filter(Dataset.id == template.dataset_id).first()
    if not dataset:
        raise ValueError("模板关联的数据集不存在")
    datasource = db.query(DataSource).filter(DataSource.id == dataset.datasource_id).first()
    if not datasource:
        raise ValueError("数据集关联的数据源不存在")

    result = _execute_dataset_preview(dataset, datasource, EXPORT_ROW_LIMIT)
    columns = [str(column) for column in (result.get("columns") or [])]
    rows = [dict(row) for row in (result.get("rows") or [])]
    parameters = run.parameters_json if isinstance(run.parameters_json, dict) else {}
    path = build_excel_file(template, dataset, columns, rows, parameters, get_export_dir(), run.id)
    return path, len(rows)
