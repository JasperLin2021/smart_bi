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

    def test_execute_report_export_writes_pdf_and_word(self):
        """PDF/Word 渲染器与 Excel 共用取数结果，产物后缀与内容正确。"""
        from app.core.report_exporter import execute_report_export

        db = _db()
        template = _make_template(db, layout={"paper": "A4", "cells": [{"row": 1, "col": 1, "value": "区域: {{region}}"}]})
        db.add_all(
            [
                DataSource(id=1, name="主库", slug="main", database_url="sqlite:///:memory:", is_active=1, org_id=1, metadata_prompt="schema"),
                Dataset(id=1, name="销售明细", datasource_id=1, org_id=1),
            ]
        )
        db.commit()
        fake_result = {
            "columns": ["region", "amount"],
            "rows": [
                {"region": "华东", "amount": 100},
                {"region": "华北", "amount": None},
            ],
        }
        for export_type, suffix in (("pdf", ".pdf"), ("word", ".docx")):
            run = ReportRun(
                template_id=template.id,
                version=template.version,
                run_type="export",
                export_type=export_type,
                status="running",
                parameters_json={"region": "华东"},
                org_id=1,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            with patch("app.api.datasets._execute_dataset_preview", return_value=fake_result):
                path, row_count = execute_report_export(db, template, run)
            self.assertEqual(row_count, 2)
            self.assertTrue(Path(path).exists())
            self.assertGreater(Path(path).stat().st_size, 0)
            self.assertTrue(path.name.endswith(suffix))
            Path(path).unlink(missing_ok=True)

    def test_execute_report_export_writes_html_for_unbound_ai_template(self):
        """无数据集的 ai_html 模板：导出 html 时落盘 layout html，并内联 echarts 使其离线可用。"""
        from app.core.report_exporter import execute_report_export

        db = _db()
        source_html = (
            "<!DOCTYPE html><html><head>"
            '<script src="/report-libs/echarts.min.js"></script>'
            "</head><body><h1>经营分析</h1>"
            '<div id="chart" style="height:300px"></div>'
            '<script>echarts.init(document.getElementById("chart"))</script>'
            "</body></html>"
        )
        template = ReportTemplate(
            name="AI 经营分析",
            dataset_id=None,
            version=1,
            layout_json={"kind": "html", "html": source_html},
            org_id=1,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        run = ReportRun(
            template_id=template.id,
            version=1,
            run_type="export",
            export_type="html",
            status="running",
            org_id=1,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        path, row_count = execute_report_export(db, template, run)
        self.assertEqual(row_count, 0)
        self.assertTrue(Path(path).exists())
        self.assertTrue(path.name.endswith(".html"))
        content = Path(path).read_text(encoding="utf-8")
        self.assertIn("经营分析", content)
        # 站内相对路径在 file:// 下无法加载，导出时必须替换为内联 echarts 运行库
        self.assertNotIn("/report-libs/echarts.min.js", content)
        self.assertNotIn("<script src=", content)
        self.assertIn("<script>\n", content)
        Path(path).unlink(missing_ok=True)

    def test_html_export_inlines_echarts_runtime(self):
        """无 echarts 引用的 html 原样返回；有引用的被替换为内联内容（后端已 vendor 该库）。"""
        from app.core.report_exporter import _ECHARTS_RELATIVE_SRC, _inline_echarts_runtime

        plain = "<p>无图表内容</p>"
        self.assertEqual(_inline_echarts_runtime(plain), plain)

        source = f"<p>before</p><script src=\"{_ECHARTS_RELATIVE_SRC}\"></script><p>after</p>"
        result = _inline_echarts_runtime(source)
        self.assertNotIn(_ECHARTS_RELATIVE_SRC, result)
        # 内联脚本替换原位置，且保留前后内容与内联库主体
        self.assertIn("<p>before</p><script>\n", result)
        self.assertIn("</script><p>after</p>", result)
        self.assertGreater(len(result), 100_000)

    def test_execute_report_export_html_without_html_content_raises(self):
        """layout 中没有 html 内容时，html 导出应明确报错而非生成空文件。"""
        from app.core.report_exporter import execute_report_export

        db = _db()
        template = _make_template(db, layout={"paper": "A4"})  # 无 html 字段
        run = ReportRun(
            template_id=template.id,
            version=1,
            run_type="export",
            export_type="html",
            status="running",
            org_id=1,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        with self.assertRaises(ValueError) as ctx:
            execute_report_export(db, template, run)
        self.assertIn("HTML", str(ctx.exception))

    def test_export_endpoint_rejects_bounded_formats_for_unbound_template(self):
        """无数据集模板只能导出 html；excel/pdf/word 在端点上应早期返回 400。"""
        from fastapi import HTTPException

        from app.api.report_templates import export_report_template
        from app.schemas.report_template import ReportExportRequest

        db = _db()
        template = ReportTemplate(
            name="AI 经营分析",
            dataset_id=None,
            version=1,
            layout_json={"kind": "html", "html": "<h1>经营分析</h1>"},
            org_id=1,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        user = SimpleNamespace(id=5, role="org_admin", org_id=1)

        with patch("app.core.permissions.require_action", return_value=None):
            with patch("app.api.report_templates._get_template_for_user", return_value=template):
                for export_type in ("excel", "pdf", "word"):
                    with self.assertRaises(HTTPException) as ctx:
                        export_report_template(
                            template.id,
                            ReportExportRequest(export_type=export_type),
                            db=db,
                            current_user=user,
                        )
                    self.assertEqual(ctx.exception.status_code, 400)
                    self.assertIn("HTML", ctx.exception.detail)
        # 空运行记录：拒绝发生在创建 ReportRun 之前
        self.assertEqual(db.query(ReportRun).count(), 0)

    def test_download_endpoint_returns_media_type_by_suffix(self):
        """下载响应按导出文件后缀返回对应 MIME（pdf/docx/html 不再固定为 xlsx）。"""
        from fastapi.responses import FileResponse

        from app.api.report_templates import download_report_run

        db = _db()
        template = _make_template(db)
        export_dir = Path(__file__).resolve().parents[1] / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        cases = {
            "sample.pdf": "application/pdf",
            "sample.docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "sample.html": "text/html; charset=utf-8",
        }
        try:
            for filename, expected_media_type in cases.items():
                fake_file = export_dir / filename
                fake_file.write_bytes(b"fake")
                run = ReportRun(
                    template_id=template.id,
                    version=1,
                    run_type="export",
                    export_type="excel",
                    status="completed",
                    output_uri=filename,
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
                self.assertEqual(response.media_type, expected_media_type)
                db.delete(run)
                db.commit()
        finally:
            for filename in cases:
                Path(export_dir / filename).unlink(missing_ok=True)


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
