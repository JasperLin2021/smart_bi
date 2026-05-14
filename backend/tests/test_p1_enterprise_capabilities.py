import os
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class P1EnterpriseCapabilityTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _pipeline_source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE daily_operations (
                      work_date TEXT NOT NULL,
                      line TEXT NOT NULL,
                      oee REAL,
                      revenue REAL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO daily_operations (work_date, line, oee, revenue)
                    VALUES
                      ('2026-05-01', 'A', 91.5, 12000),
                      ('2026-05-02', 'B', 88.0, 9800),
                      ('2026-05-03', 'A', 92.1, 13500)
                    """
                )
            )
        engine.dispose()
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    def _attach_pipeline_source(self, db):
        from app.models.datasource import DataSource

        source_path = self._pipeline_source_database()
        datasource = db.query(DataSource).filter(DataSource.id == 101).one()
        datasource.database_url = f"sqlite:///{source_path}"
        db.commit()

    def _seed_dataset(self, db):
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db.add_all(
            [
                Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                Organization(id=2, name="Orion Retail Group", slug="orion-retail"),
                User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                User(id=11, username="nova.viewer", hashed_password="x", role="user", org_id=1),
                User(id=20, username="orion.admin", hashed_password="x", role="org_admin", org_id=2),
                DataSource(
                    id=101,
                    name="Nova ERP Warehouse",
                    slug="nova-erp",
                    database_url="sqlite:///:memory:",
                    source_type="database",
                    metadata_prompt="production, quality and sales marts",
                    org_id=1,
                ),
                DataSource(
                    id=201,
                    name="Orion POS Mart",
                    slug="orion-pos",
                    database_url="sqlite:///:memory:",
                    source_type="database",
                    metadata_prompt="retail basket lines",
                    org_id=2,
                ),
                Dataset(
                    id=301,
                    name="Nova Daily Operations",
                    description="Production, OEE and shipment dataset for plant leaders.",
                    datasource_id=101,
                    fields_json={
                        "table": "daily_operations",
                        "fields": [
                            {"name": "daily_operations.work_date", "type": "date", "role": "dimension"},
                            {"name": "daily_operations.line", "type": "string", "role": "dimension"},
                            {"name": "daily_operations.oee", "type": "decimal", "role": "metric"},
                            {"name": "daily_operations.revenue", "type": "decimal", "role": "metric"},
                        ],
                    },
                    semantic_model_json={
                        "dimensions": [{"name": "line", "label": "产线"}],
                        "measures": [{"name": "oee", "label": "OEE", "aggregation": "avg"}],
                    },
                    status="published",
                    visibility="org",
                    org_id=1,
                    owner_id=10,
                ),
                Dataset(
                    id=401,
                    name="Orion Basket Analytics",
                    datasource_id=201,
                    fields_json={"table": "basket_lines", "fields": ["basket_lines.store_id"]},
                    status="published",
                    visibility="org",
                    org_id=2,
                    owner_id=20,
                ),
            ]
        )
        db.commit()

    def test_report_template_lifecycle_enforces_permissions_and_versions(self):
        from app.api.report_templates import create_report_template, export_report_template, list_report_versions
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.report_template import ReportRun, ReportTemplate, ReportTemplateVersion
        from app.models.user import User
        from app.schemas.report_template import ReportExportRequest, ReportTemplateCreate

        db = self._db(
            [
                User.__table__,
                Organization.__table__,
                DataSource.__table__,
                Dataset.__table__,
                ReportTemplate.__table__,
                ReportTemplateVersion.__table__,
                ReportRun.__table__,
                AuditLog.__table__,
            ]
        )
        self._seed_dataset(db)

        viewer = SimpleNamespace(id=11, username="nova.viewer", role="user", org_id=1)
        with self.assertRaises(HTTPException) as denied:
            create_report_template(
                ReportTemplateCreate(name="OEE 周报", dataset_id=301, report_type="paginated"),
                db=db,
                current_user=viewer,
            )
        self.assertEqual(denied.exception.status_code, 403)

        admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
        report = create_report_template(
            ReportTemplateCreate(
                name="Nova OEE 周报",
                dataset_id=301,
                report_type="paginated",
                layout_json={"paper": "A4", "cells": [{"row": 1, "col": 1, "value": "{{ line }}"}]},
                parameter_schema_json={"line": {"type": "string", "label": "产线"}},
                binding_json={"bands": [{"dataset_id": 301, "repeat": "detail"}]},
                fill_schema_json={"fields": [{"name": "manager_comment", "required": True}]},
                visibility="org",
            ),
            db=db,
            current_user=admin,
        )

        self.assertEqual(report.org_id, 1)
        self.assertEqual(report.dataset_id, 301)
        self.assertEqual(report.version, 1)
        versions = list_report_versions(report.id, db=db, current_user=admin)
        self.assertEqual(len(versions), 1)

        exported = export_report_template(
            report.id,
            ReportExportRequest(export_type="excel", parameters={"line": "A1"}),
            db=db,
            current_user=admin,
        )
        self.assertEqual(exported["status"], "queued")
        self.assertEqual(exported["export_type"], "excel")
        self.assertEqual(db.query(ReportRun).filter(ReportRun.template_id == report.id).count(), 1)

    def test_data_pipeline_dag_run_quality_rule_and_org_scope(self):
        from app.api.pipelines import create_pipeline, create_quality_rule, get_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest, QualityRuleCreate

        db = self._db(
            [
                User.__table__,
                Organization.__table__,
                DataSource.__table__,
                Dataset.__table__,
                DatasetRefreshLog.__table__,
                DataPipeline.__table__,
                DataPipelineRun.__table__,
                DataQualityRule.__table__,
                AuditLog.__table__,
            ]
        )
        self._seed_dataset(db)
        self._attach_pipeline_source(db)

        admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
        pipeline = create_pipeline(
            PipelineCreate(
                name="Nova ERP 到经营数据集",
                dataset_id=301,
                dag_json={
                    "nodes": [
                        {"id": "extract_erp", "type": "extract", "label": "抽取 ERP"},
                        {"id": "clean_quality", "type": "transform", "label": "清洗质检"},
                        {"id": "load_dataset", "type": "load", "label": "写入数据集"},
                    ],
                    "edges": [
                        {"source": "extract_erp", "target": "clean_quality"},
                        {"source": "clean_quality", "target": "load_dataset"},
                    ],
                },
                schedule_cron="0 2 * * *",
            ),
            db=db,
            current_user=admin,
        )
        self.assertEqual(pipeline.org_id, 1)
        self.assertEqual(pipeline.status, "draft")

        rule = create_quality_rule(
            QualityRuleCreate(
                pipeline_id=pipeline.id,
                dataset_id=301,
                name="OEE 完整性",
                rule_type="not_null",
                field="oee",
                severity="error",
            ),
            db=db,
            current_user=admin,
        )
        self.assertEqual(rule.pipeline_id, pipeline.id)

        run = run_pipeline(
            pipeline.id,
            PipelineRunRequest(mode="backfill", reason="补齐本周数据"),
            db=db,
            current_user=admin,
        )
        self.assertEqual(run.status, "success")
        self.assertEqual(run.mode, "backfill")
        self.assertEqual(run.node_logs_json["summary"]["node_count"], 3)

        orion_admin = SimpleNamespace(id=20, username="orion.admin", role="org_admin", org_id=2)
        with self.assertRaises(HTTPException) as hidden:
            get_pipeline(pipeline.id, db=db, current_user=orion_admin)
        self.assertEqual(hidden.exception.status_code, 404)

    def test_enterprise_pipeline_validation_blocks_cycles_and_tracks_backfill_window(self):
        from datetime import datetime

        from app.api.pipelines import create_pipeline, run_pipeline, validate_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        db = self._db(
            [
                User.__table__,
                Organization.__table__,
                DataSource.__table__,
                Dataset.__table__,
                DatasetRefreshLog.__table__,
                DataPipeline.__table__,
                DataPipelineRun.__table__,
                DataQualityRule.__table__,
                AuditLog.__table__,
            ]
        )
        self._seed_dataset(db)
        self._attach_pipeline_source(db)
        admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

        with self.assertRaises(HTTPException) as cycle_error:
            create_pipeline(
                PipelineCreate(
                    name="循环依赖管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract", "type": "extract", "label": "抽取"},
                            {"id": "load", "type": "load", "label": "写入"},
                        ],
                        "edges": [
                            {"source": "extract", "target": "load"},
                            {"source": "load", "target": "extract"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )
        self.assertEqual(cycle_error.exception.status_code, 400)
        self.assertIn("循环依赖", cycle_error.exception.detail)

        with self.assertRaises(HTTPException) as cron_error:
            create_pipeline(
                PipelineCreate(
                    name="缺少调度表达式",
                    dataset_id=301,
                    run_mode="scheduled",
                    dag_json={
                        "nodes": [
                            {"id": "extract", "type": "extract", "label": "抽取"},
                            {"id": "load", "type": "load", "label": "写入"},
                        ],
                        "edges": [{"source": "extract", "target": "load"}],
                    },
                ),
                db=db,
                current_user=admin,
            )
        self.assertEqual(cron_error.exception.status_code, 400)
        self.assertIn("Cron", cron_error.exception.detail)

        pipeline = create_pipeline(
            PipelineCreate(
                name="Nova ERP 增量加工",
                dataset_id=301,
                dag_json={
                    "nodes": [
                        {"id": "extract_erp", "type": "extract", "label": "抽取 ERP"},
                        {"id": "normalize", "type": "transform", "label": "标准化字段"},
                        {"id": "quality_gate", "type": "quality", "label": "质量闸门"},
                        {"id": "load_dataset", "type": "load", "label": "写入经营数据集"},
                    ],
                    "edges": [
                        {"source": "extract_erp", "target": "normalize"},
                        {"source": "normalize", "target": "quality_gate"},
                        {"source": "quality_gate", "target": "load_dataset"},
                    ],
                },
                schedule_cron="0 2 * * *",
                run_mode="scheduled",
                environment="prod",
                priority="high",
                sla_minutes=90,
                retry_count=3,
                timeout_minutes=45,
                alert_policy_json={"channels": ["wechat_work"], "on_failure": True},
            ),
            db=db,
            current_user=admin,
        )
        self.assertEqual(pipeline.environment, "prod")
        self.assertEqual(pipeline.priority, "high")
        self.assertEqual(pipeline.sla_minutes, 90)

        validation = validate_pipeline(pipeline.id, db=db, current_user=admin)
        self.assertEqual(validation.status, "warning")
        self.assertEqual(validation.critical_count, 0)
        self.assertTrue(any(item.code == "missing_quality_rules" for item in validation.diagnostics))
        self.assertEqual(validation.node_count, 4)
        self.assertEqual(validation.schedule_cron, "0 2 * * *")

        run = run_pipeline(
            pipeline.id,
            PipelineRunRequest(
                mode="backfill",
                reason="补齐五一假期数据",
                window_start=datetime(2026, 5, 1, 0, 0, 0),
                window_end=datetime(2026, 5, 5, 23, 59, 59),
                dry_run=True,
            ),
            db=db,
            current_user=admin,
        )
        self.assertEqual(run.status, "success")
        self.assertEqual(run.records_written, 0)
        self.assertTrue(run.node_logs_json["summary"]["dry_run"])
        self.assertEqual(run.node_logs_json["summary"]["run_window"]["start"], "2026-05-01T00:00:00")
        self.assertEqual(run.node_logs_json["summary"]["retry_count"], 3)

    def test_analysis_view_builds_workbench_config_and_blocks_cross_org_dataset(self):
        from app.api.analysis_views import create_analysis_view, preview_analysis_view
        from app.models.analysis_view import AnalysisView
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.analysis_view import AnalysisPreviewRequest, AnalysisViewCreate

        db = self._db([User.__table__, Organization.__table__, DataSource.__table__, Dataset.__table__, AnalysisView.__table__, AuditLog.__table__])
        self._seed_dataset(db)

        analyst = SimpleNamespace(id=11, username="nova.viewer", role="user", org_id=1)
        view = create_analysis_view(
            AnalysisViewCreate(
                name="Nova 产线 OEE 自助分析",
                dataset_id=301,
                chart_type="line",
                dimensions=["line"],
                measures=[{"field": "oee", "aggregation": "avg", "alias": "平均 OEE"}],
                filters=[{"field": "work_date", "operator": ">=", "value": "2026-05-01"}],
            ),
            db=db,
            current_user=analyst,
        )
        self.assertEqual(view.owner_id, 11)
        self.assertEqual(view.org_id, 1)

        preview = preview_analysis_view(
            view.id,
            AnalysisPreviewRequest(limit=100),
            db=db,
            current_user=analyst,
        )
        self.assertEqual(preview["chart"]["type"], "line")
        self.assertEqual(preview["dataset"]["name"], "Nova Daily Operations")
        self.assertIn("SELECT", preview["query_plan"]["sql"])
        self.assertEqual(preview["query_plan"]["limit"], 100)

        with self.assertRaises(HTTPException) as denied:
            create_analysis_view(
                AnalysisViewCreate(name="越权分析", dataset_id=401, chart_type="bar", dimensions=["store_id"]),
                db=db,
                current_user=analyst,
            )
        self.assertEqual(denied.exception.status_code, 404)

    def test_permission_catalog_exposes_report_pipeline_analysis_capabilities(self):
        from app.core.permissions import get_role_permission_template

        super_admin = get_role_permission_template("super_admin")
        org_admin = get_role_permission_template("org_admin")
        user = get_role_permission_template("user")

        for key in ("report_center.view", "data_pipeline.view", "analysis_workbench.view"):
            self.assertTrue(super_admin["menu_permissions"][key])

        self.assertTrue(org_admin["action_permissions"]["report.create"])
        self.assertTrue(org_admin["action_permissions"]["pipeline.run"])
        self.assertTrue(user["action_permissions"]["analysis.create"])
        self.assertFalse(user["action_permissions"]["pipeline.run"])

    def test_safe_delete_blocks_dataset_used_by_p1_assets(self):
        from app.core.safe_delete import assert_dataset_can_delete
        from app.models.action_item import ActionItem
        from app.models.analysis_view import AnalysisView
        from app.models.big_screen import BigScreen
        from app.models.catalog import DataAsset
        from app.models.dashboard_config import Dashboard
        from app.models.data_pipeline import DataPipeline
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization
        from app.models.report_template import ReportTemplate
        from app.models.scheduled_report import ScheduledReport
        from app.models.user import User

        db = self._db(
            [
                DataSource.__table__,
                Organization.__table__,
                User.__table__,
                Dataset.__table__,
                Metric.__table__,
                ActionItem.__table__,
                Dashboard.__table__,
                BigScreen.__table__,
                DataAsset.__table__,
                ScheduledReport.__table__,
                ReportTemplate.__table__,
                DataPipeline.__table__,
                AnalysisView.__table__,
            ]
        )
        self._seed_dataset(db)
        db.add_all(
            [
                ReportTemplate(name="Nova 质量月报", dataset_id=301, report_type="paginated", org_id=1),
                DataPipeline(name="Nova 数据补数", dataset_id=301, dag_json={"nodes": []}, org_id=1),
                AnalysisView(name="Nova 自助分析", dataset_id=301, chart_type="bar", org_id=1),
            ]
        )
        db.commit()

        dataset = db.query(Dataset).filter(Dataset.id == 301).one()
        with self.assertRaises(HTTPException) as blocked:
            assert_dataset_can_delete(db, dataset)
        self.assertEqual(blocked.exception.status_code, 409)
        self.assertIn("复杂报表", blocked.exception.detail)
        self.assertIn("数据集成管道", blocked.exception.detail)
        self.assertIn("自助分析", blocked.exception.detail)


if __name__ == "__main__":
    unittest.main()
