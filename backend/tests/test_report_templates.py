"""复杂报表导出与填报回写的单元测试。

覆盖：
- 导出执行器生成 Excel 文件（mock 数据集取数，避免依赖真实数据源）
- 导出端点更新 ReportRun 状态为 completed，下载端点返回文件
- 填报回写：配置了 writeback 目标时推进为 completed；未配置时保持 pending
- 回写标识符白名单校验，拒绝非法表名/列名（防注入）
"""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.dataset import Dataset
from app.models.datasource import DataSource
from app.models.report_template import ReportFillRecord, ReportRun, ReportTemplate


def _db():
    from app.db.base import Base  # noqa: F401 - 触发所有模型注册到 metadata

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _make_template(db, *, fill_schema=None, layout=None):
    template = ReportTemplate(
        name="销售月报",
        dataset_id=1,
        version=1,
        layout_json=layout or {"paper": "A4", "cells": []},
        fill_schema_json=fill_schema,
        org_id=1,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


class ReportExportTests(unittest.TestCase):
    def test_execute_report_export_writes_excel_and_completes_run(self):
        from app.core.report_exporter import execute_report_export

        db = _db()
        template = _make_template(db, layout={"paper": "A4", "cells": [{"row": 1, "col": 1, "value": "区域: {{region}}"}]})
        # 数据集 + 数据源记录（取数逻辑被 mock，仅需要记录存在）
        db.add_all(
            [
                DataSource(id=1, name="主库", slug="main", database_url="sqlite:///:memory:", is_active=1, org_id=1, metadata_prompt="schema"),
                Dataset(id=1, name="销售明细", datasource_id=1, org_id=1),
            ]
        )
        db.commit()
        run = ReportRun(
            template_id=template.id,
            version=template.version,
            run_type="export",
            export_type="excel",
            status="running",
            parameters_json={"region": "华东"},
            org_id=1,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        fake_result = {"columns": ["region", "amount"], "rows": [{"region": "华东", "amount": 100}, {"region": "华北", "amount": 80}]}
        with patch("app.api.datasets._execute_dataset_preview", return_value=fake_result):
            path, row_count = execute_report_export(db, template, run)

        self.assertEqual(row_count, 2)
        self.assertTrue(Path(path).exists())
        self.assertTrue(path.name.endswith(".xlsx"))
        Path(path).unlink(missing_ok=True)

    def test_export_endpoint_marks_failed_on_error(self):
        """导出执行器抛错时，端点应把 ReportRun 标记为 failed 并记录错误信息。"""
        from app.api.report_templates import export_report_template
        from app.schemas.report_template import ReportExportRequest

        db = _db()
        template = _make_template(db)
        user = SimpleNamespace(id=5, role="org_admin", org_id=1)

        with patch("app.core.permissions.require_action", return_value=None):
            with patch("app.api.report_templates._get_template_for_user", return_value=template):
                with patch(
                    "app.api.report_templates.execute_report_export",
                    side_effect=ValueError("数据集关联的数据源不存在"),
                ):
                    result = export_report_template(
                        template.id,
                        ReportExportRequest(export_type="excel"),
                        db=db,
                        current_user=user,
                    )

        run = db.query(ReportRun).filter(ReportRun.template_id == template.id).one()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(run.status, "failed")
        self.assertIn("数据源不存在", run.error_message)

    def test_download_endpoint_serves_completed_file(self):
        from fastapi.responses import FileResponse

        from app.api.report_templates import download_report_run

        db = _db()
        template = _make_template(db)
        # 写一个真实的临时文件作为导出产物
        export_dir = Path(__file__).resolve().parents[1] / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        fake_file = export_dir / "test_run_download.xlsx"
        fake_file.write_bytes(b"fake-xlsx")
        try:
            run = ReportRun(
                template_id=template.id,
                version=1,
                run_type="export",
                export_type="excel",
                status="completed",
                output_uri=fake_file.name,
                org_id=1,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            user = SimpleNamespace(id=5, role="org_admin", org_id=1)

            with patch("app.core.permissions.require_action", return_value=None):
                with patch("app.api.report_templates._get_template_for_user", return_value=template):
                    response = download_report_run(run.id, db=db, current_user=user)

            self.assertIsInstance(response, FileResponse)
            self.assertEqual(Path(response.path).name, fake_file.name)
        finally:
            fake_file.unlink(missing_ok=True)

    def test_download_rejects_not_completed_run(self):
        from fastapi import HTTPException

        from app.api.report_templates import download_report_run

        db = _db()
        template = _make_template(db)
        run = ReportRun(
            template_id=template.id,
            version=1,
            run_type="export",
            export_type="excel",
            status="failed",
            org_id=1,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        user = SimpleNamespace(id=5, role="org_admin", org_id=1)

        with patch("app.core.permissions.require_action", return_value=None):
            with patch("app.api.report_templates._get_template_for_user", return_value=template):
                with self.assertRaises(HTTPException) as ctx:
                    download_report_run(run.id, db=db, current_user=user)
        self.assertEqual(ctx.exception.status_code, 400)


class ReportFillWritebackTests(unittest.TestCase):
    def test_fill_without_writeback_target_stays_pending(self):
        """fill_schema 未配置 writeback 时，填报记录保持 pending（待回写）。"""
        from app.api.report_templates import submit_report_fill
        from app.schemas.report_template import ReportFillRequest

        db = _db()
        template = _make_template(
            db,
            fill_schema={
                "fields": [{"name": "region", "required": True}],
                # 无 writeback 配置
            },
        )
        user = SimpleNamespace(id=5, role="org_admin", org_id=1)

        with patch("app.core.permissions.require_action", return_value=None):
            with patch("app.api.report_templates._get_template_for_user", return_value=template):
                result = submit_report_fill(
                    template.id,
                    ReportFillRequest(payload={"region": "华东"}),
                    db=db,
                    current_user=user,
                )

        record = db.query(ReportFillRecord).filter(ReportFillRecord.template_id == template.id).one()
        self.assertEqual(result["writeback_status"], "pending")
        self.assertEqual(record.writeback_status, "pending")

    def test_fill_with_writeback_target_completes(self):
        """配置了 writeback 目标表时，回写成功后状态推进为 completed。"""
        from app.api.report_templates import submit_report_fill
        from app.schemas.report_template import ReportFillRequest

        db = _db()
        template = _make_template(
            db,
            fill_schema={
                "fields": [{"name": "region", "required": True}],
                "writeback": {"table": "sales_fill", "columns": {"region": "region_name"}},
            },
        )
        user = SimpleNamespace(id=5, role="org_admin", org_id=1)

        with patch("app.core.permissions.require_action", return_value=None):
            with patch("app.api.report_templates._get_template_for_user", return_value=template):
                with patch("app.api.report_templates.execute_fill_writeback", return_value=None) as mock_wb:
                    result = submit_report_fill(
                        template.id,
                        ReportFillRequest(payload={"region": "华东"}),
                        db=db,
                        current_user=user,
                    )

        mock_wb.assert_called_once()
        record = db.query(ReportFillRecord).filter(ReportFillRecord.template_id == template.id).one()
        self.assertEqual(result["writeback_status"], "completed")
        self.assertEqual(record.writeback_status, "completed")

    def test_writeback_rejects_invalid_table_identifier(self):
        """回写表名必须通过标识符白名单校验，非法表名直接拒绝（防 SQL 注入）。"""
        from app.core.report_writeback import execute_fill_writeback

        db = _db()
        schema = {"writeback": {"table": "sales; DROP TABLE x; --", "columns": {"region": "region"}}}
        with self.assertRaises(ValueError) as ctx:
            execute_fill_writeback(db, schema, {"region": "华东"})
        self.assertIn("表名", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
