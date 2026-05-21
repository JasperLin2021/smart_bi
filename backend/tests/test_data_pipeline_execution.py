import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class DataPipelineExecutionTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _http_db(self, tables):
        from app.db.base_class import Base

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _source_database(self, rows):
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
                    VALUES (:work_date, :line, :oee, :revenue)
                    """
                ),
                rows,
            )
        engine.dispose()
        return path

    def _order_source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE order_events (
                      order_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount REAL,
                      discount REAL,
                      region TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO order_events (order_id, status, amount, discount, region)
                    VALUES (:order_id, :status, :amount, :discount, :region)
                    """
                ),
                [
                    {"order_id": "O001", "status": "PAID", "amount": 100.0, "discount": 10.0, "region": "East"},
                    {"order_id": "O001", "status": "PAID", "amount": 100.0, "discount": 10.0, "region": "East"},
                    {"order_id": "O002", "status": "PENDING", "amount": 60.0, "discount": 0.0, "region": "East"},
                    {"order_id": "O003", "status": "COMPLETE", "amount": 200.0, "discount": 20.0, "region": "West"},
                ],
            )
        engine.dispose()
        return path

    def _excel_order_source_file(self):
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        pd.DataFrame(
            [
                {"order_id": "ORD001", "order_date": "2026-05-14", "status": "已完成", "total_amount": 1200},
                {"order_id": "ORD002", "order_date": "2026-05-15", "status": "已完成", "total_amount": 800},
            ]
        ).to_excel(path, sheet_name="orders", index=False)
        return path

    def _multi_source_database(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE order_events (
                      order_id TEXT NOT NULL,
                      status TEXT NOT NULL,
                      amount REAL,
                      discount REAL,
                      region TEXT,
                      updated_at TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE region_targets (
                      region TEXT NOT NULL,
                      target_margin REAL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO order_events (order_id, status, amount, discount, region, updated_at)
                    VALUES (:order_id, :status, :amount, :discount, :region, :updated_at)
                    """
                ),
                [
                    {"order_id": "O001", "status": "PAID", "amount": 100.0, "discount": 10.0, "region": "East", "updated_at": "2026-05-01T08:00:00"},
                    {"order_id": "O001", "status": "PAID", "amount": 100.0, "discount": 10.0, "region": "East", "updated_at": "2026-05-01T09:00:00"},
                    {"order_id": "O002", "status": "PENDING", "amount": 60.0, "discount": 0.0, "region": "East", "updated_at": "2026-05-02T08:00:00"},
                    {"order_id": "O003", "status": "COMPLETE", "amount": 200.0, "discount": 20.0, "region": "West", "updated_at": "2026-05-03T08:00:00"},
                ],
            )
            conn.execute(
                text("INSERT INTO region_targets (region, target_margin) VALUES (:region, :target_margin)"),
                [
                    {"region": "East", "target_margin": 0.18},
                    {"region": "West", "target_margin": 0.22},
                ],
            )
        engine.dispose()
        return path

    def _seed_pipeline_fixture(self, db, source_path: str):
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db.add_all(
            [
                Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                DataSource(
                    id=101,
                    name="Nova ERP Warehouse",
                    slug="nova-erp",
                    database_url=f"sqlite:///{source_path}",
                    source_type="database",
                    metadata_prompt="production facts",
                    org_id=1,
                ),
                Dataset(
                    id=301,
                    name="Nova Daily Operations",
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
                    status="published",
                    visibility="org",
                    org_id=1,
                    owner_id=10,
                ),
            ]
        )
        db.commit()

    def _seed_multi_dataset_fixture(self, db, source_path: str):
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        db.add_all(
            [
                Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                DataSource(
                    id=101,
                    name="Nova ERP Warehouse",
                    slug="nova-erp",
                    database_url=f"sqlite:///{source_path}",
                    source_type="database",
                    metadata_prompt="orders and region targets",
                    org_id=1,
                ),
                Dataset(
                    id=301,
                    name="Nova Orders",
                    datasource_id=101,
                    fields_json={
                        "table": "order_events",
                        "fields": [
                            "order_events.order_id",
                            "order_events.status",
                            "order_events.amount",
                            "order_events.discount",
                            "order_events.region",
                            "order_events.updated_at",
                        ],
                    },
                    status="published",
                    visibility="org",
                    org_id=1,
                    owner_id=10,
                ),
                Dataset(
                    id=302,
                    name="Nova Region Targets",
                    datasource_id=101,
                    fields_json={
                        "table": "region_targets",
                        "fields": [
                            "region_targets.region",
                            "region_targets.target_margin",
                        ],
                    },
                    status="published",
                    visibility="org",
                    org_id=1,
                    owner_id=10,
                ),
            ]
        )
        db.commit()

    def _pipeline_payload(self):
        from app.schemas.pipeline import PipelineCreate

        return PipelineCreate(
            name="Nova 生产经营日加工",
            dataset_id=301,
            run_mode="manual",
            dag_json={
                "nodes": [
                    {"id": "extract", "type": "extract", "label": "抽取生产明细"},
                    {"id": "quality", "type": "quality", "label": "质量闸门"},
                    {"id": "load", "type": "load", "label": "刷新目标数据集"},
                ],
                "edges": [
                    {"source": "extract", "target": "quality"},
                    {"source": "quality", "target": "load"},
                ],
            },
        )

    def _order_pipeline_payload(self):
        from app.schemas.pipeline import PipelineCreate

        return PipelineCreate(
            name="订单事实清洗聚合",
            dataset_id=301,
            run_mode="manual",
            dag_json={
                "nodes": [
                    {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                    {
                        "id": "shape_orders",
                        "type": "transform",
                        "label": "字段映射与聚合",
                        "config": {
                            "field_mapping": [
                                {"source": "region", "target": "area"},
                            ],
                            "type_conversions": [
                                {"field": "amount", "type": "decimal"},
                                {"field": "discount", "type": "decimal"},
                            ],
                            "filters": [
                                {"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]},
                            ],
                            "derived_columns": [
                                {"name": "net_amount", "expression": "amount - discount"},
                            ],
                            "dedupe": {"keys": ["order_id"], "keep": "first"},
                            "aggregations": {
                                "group_by": ["area"],
                                "metrics": [
                                    {"field": "net_amount", "function": "sum", "alias": "net_amount_sum"},
                                    {"field": "order_id", "function": "count", "alias": "order_count"},
                                ],
                            },
                        },
                    },
                    {"id": "quality_orders", "type": "quality", "label": "质量闸门"},
                    {
                        "id": "load_orders",
                        "type": "load",
                        "label": "输出订单分析集",
                        "config": {"target_table": "etl_order_summary", "mode": "replace"},
                    },
                ],
                "edges": [
                    {"source": "extract_orders", "target": "shape_orders"},
                    {"source": "shape_orders", "target": "quality_orders"},
                    {"source": "quality_orders", "target": "load_orders"},
                ],
            },
        )

    def test_pipeline_operator_catalog_exposes_enterprise_low_code_contract(self):
        from app.api.pipelines import list_pipeline_operators

        operators = list_pipeline_operators(current_user=SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1))
        by_type = {item["type"]: item for item in operators}

        self.assertIn("extract", by_type)
        self.assertIn("metadata_extract", by_type)
        self.assertIn("sql", by_type)
        self.assertIn("reverse_etl", by_type)
        self.assertEqual(by_type["sql"]["category"], "SQL/ELT")
        self.assertIn("execution_mode", by_type["sql"]["config_schema"]["properties"])
        self.assertIn("primary_key", by_type["reverse_etl"]["config_schema"]["properties"])
        self.assertIn("batch_size", by_type["load"]["config_schema"]["properties"])
        self.assertIn("batch_size", by_type["reverse_etl"]["config_schema"]["properties"])
        self.assertEqual(by_type["reverse_etl"]["default_config"]["mode"], "upsert")
        self.assertGreaterEqual(len(by_type["join"]["input_ports"]), 2)

    def test_pipeline_run_extracts_real_dataset_rows_and_refreshes_dataset(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineRunRequest

        source_path = self._source_database(
            [
                {"work_date": "2026-05-01", "line": "A", "oee": 91.5, "revenue": 12000},
                {"work_date": "2026-05-02", "line": "B", "oee": 88.0, "revenue": 9800},
            ]
        )
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._pipeline_payload(), db=db, current_user=admin)

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="真实抽取验证"),
                db=db,
                current_user=admin,
            )

            dataset = db.query(Dataset).filter(Dataset.id == 301).one()
            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 2)
            self.assertEqual(run.records_written, 2)
            self.assertEqual(run.node_logs_json["summary"]["source_row_count"], 2)
            self.assertEqual(dataset.last_refresh_status, "success")
            self.assertEqual(dataset.last_refresh_row_count, 2)
            self.assertEqual(db.query(DatasetRefreshLog).filter(DatasetRefreshLog.dataset_id == 301).count(), 1)
        finally:
            os.unlink(source_path)

    def test_pipeline_run_executes_quality_rules_and_persists_failed_run(self):
        from app.api.pipelines import create_pipeline, create_quality_rule, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineRunRequest, QualityRuleCreate

        source_path = self._source_database(
            [
                {"work_date": "2026-05-01", "line": "A", "oee": 91.5, "revenue": 12000},
                {"work_date": "2026-05-02", "line": "B", "oee": None, "revenue": 9800},
            ]
        )
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._pipeline_payload(), db=db, current_user=admin)
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

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="质量规则验证"),
                db=db,
                current_user=admin,
            )

            db.refresh(rule)
            dataset = db.query(Dataset).filter(Dataset.id == 301).one()
            db.refresh(pipeline)
            self.assertEqual(run.status, "failed")
            self.assertEqual(run.records_read, 2)
            self.assertEqual(run.records_written, 0)
            self.assertEqual(run.records_failed, 1)
            self.assertIn("OEE 完整性", run.error_message)
            self.assertEqual(run.node_logs_json["summary"]["quality"], "failed")
            self.assertEqual(run.node_logs_json["nodes"][-1]["status"], "skipped")
            self.assertEqual(rule.last_status, "failed")
            self.assertEqual(dataset.last_refresh_status, "error")
            self.assertEqual(pipeline.last_run_status, "failed")
        finally:
            os.unlink(source_path)

    def test_pipeline_run_executes_transform_nodes_and_writes_target_table(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineRunRequest

        source_path = self._order_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            dataset = db.query(Dataset).filter(Dataset.id == 301).one()
            dataset.fields_json = {
                "table": "order_events",
                "fields": [
                    "order_events.order_id",
                    "order_events.status",
                    "order_events.amount",
                    "order_events.discount",
                    "order_events.region",
                ],
            }
            db.commit()

            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._order_pipeline_payload(), db=db, current_user=admin)

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="执行真实转换 DAG"),
                db=db,
                current_user=admin,
            )

            db.refresh(dataset)
            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 4)
            self.assertEqual(run.records_written, 2)
            self.assertEqual(dataset.last_refresh_row_count, 2)
            self.assertEqual(run.node_logs_json["summary"]["final_columns"], ["area", "net_amount_sum", "order_count"])
            self.assertEqual(run.node_logs_json["summary"]["final_row_count"], 2)
            transform_log = next(node for node in run.node_logs_json["nodes"] if node["node_id"] == "shape_orders")
            self.assertEqual(transform_log["rows_in"], 4)
            self.assertEqual(transform_log["rows_out"], 2)

            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM etl_order_summary ORDER BY area")).fetchall()]
            engine.dispose()
            self.assertEqual(
                rows,
                [
                    {"area": "East", "net_amount_sum": 90.0, "order_count": 1},
                    {"area": "West", "net_amount_sum": 180.0, "order_count": 1},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_pipeline_preview_runs_to_selected_node_without_refreshing_dataset(self):
        from app.api.pipelines import create_pipeline, preview_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelinePreviewRequest

        source_path = self._order_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            dataset = db.query(Dataset).filter(Dataset.id == 301).one()
            dataset.fields_json = {
                "table": "order_events",
                "fields": [
                    "order_events.order_id",
                    "order_events.status",
                    "order_events.amount",
                    "order_events.discount",
                    "order_events.region",
                ],
            }
            db.commit()

            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._order_pipeline_payload(), db=db, current_user=admin)

            preview = preview_pipeline(
                pipeline.id,
                PipelinePreviewRequest(node_id="shape_orders", limit=10),
                db=db,
                current_user=admin,
            )

            db.refresh(dataset)
            self.assertEqual(preview.node_id, "shape_orders")
            self.assertEqual(preview.columns, ["area", "net_amount_sum", "order_count"])
            self.assertEqual(preview.row_count, 2)
            self.assertEqual(preview.rows[0]["area"], "East")
            self.assertIsNone(dataset.last_refresh_status)
            self.assertEqual(db.query(DataPipelineRun).count(), 0)
        finally:
            os.unlink(source_path)

    def test_pipeline_lineage_returns_source_transform_quality_and_target_impact(self):
        from app.api.pipelines import create_pipeline, get_pipeline_lineage
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        source_path = self._order_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            dataset = db.query(Dataset).filter(Dataset.id == 301).one()
            dataset.fields_json = {"table": "order_events", "fields": ["order_events.order_id"]}
            db.commit()

            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._order_pipeline_payload(), db=db, current_user=admin)

            lineage = get_pipeline_lineage(pipeline.id, db=db, current_user=admin)

            self.assertEqual(lineage.pipeline_id, pipeline.id)
            self.assertEqual(lineage.source["table"], "order_events")
            self.assertEqual(lineage.target["dataset_id"], 301)
            self.assertIn("transform", [node["type"] for node in lineage.nodes])
            self.assertIn("quality", [node["type"] for node in lineage.nodes])
            self.assertTrue(any(edge["source"] == "shape_orders" and edge["target"] == "quality_orders" for edge in lineage.edges))
        finally:
            os.unlink(source_path)

    def test_pipeline_executes_branching_join_dag_with_multiple_source_datasets(self):
        from app.api.pipelines import create_pipeline, get_pipeline_lineage, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

            pipeline = create_pipeline(
                PipelineCreate(
                    name="订单与区域目标汇合 DAG",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单", "config": {"dataset_id": 301}},
                            {"id": "extract_targets", "type": "extract", "label": "抽取目标", "config": {"dataset_id": 302}},
                            {
                                "id": "paid_orders",
                                "type": "transform",
                                "label": "有效订单",
                                "config": {
                                    "filters": [{"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]}],
                                    "derived_columns": [{"name": "net_amount", "expression": "amount - discount"}],
                                    "dedupe": {"keys": ["order_id"], "keep": "first"},
                                },
                            },
                            {
                                "id": "join_targets",
                                "type": "join",
                                "label": "按区域关联目标",
                                "config": {
                                    "left_node_id": "paid_orders",
                                    "right_node_id": "extract_targets",
                                    "left_key": "region",
                                    "right_key": "region",
                                    "join_type": "inner",
                                },
                            },
                            {
                                "id": "load_joined",
                                "type": "load",
                                "label": "写入汇合结果",
                                "config": {"target_table": "etl_joined_orders", "mode": "replace"},
                            },
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "paid_orders"},
                            {"source": "paid_orders", "target": "join_targets"},
                            {"source": "extract_targets", "target": "join_targets"},
                            {"source": "join_targets", "target": "load_joined"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="验证显式 join DAG"),
                db=db,
                current_user=admin,
            )
            lineage = get_pipeline_lineage(pipeline.id, db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 6)
            self.assertEqual(run.records_written, 2)
            self.assertEqual(run.node_logs_json["summary"]["final_row_count"], 2)
            self.assertIn("target_margin", run.node_logs_json["summary"]["final_columns"])
            self.assertEqual({item["dataset_id"] for item in lineage.source["sources"]}, {301, 302})

            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT order_id, region, net_amount, target_margin FROM etl_joined_orders ORDER BY order_id")).fetchall()]
            engine.dispose()
            self.assertEqual(
                rows,
                [
                    {"order_id": "O001", "region": "East", "net_amount": 90.0, "target_margin": 0.18},
                    {"order_id": "O003", "region": "West", "net_amount": 180.0, "target_margin": 0.22},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_pipeline_executes_fanout_union_dag(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

            pipeline = create_pipeline(
                PipelineCreate(
                    name="订单分支汇总 DAG",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单", "config": {"dataset_id": 301}},
                            {"id": "east_orders", "type": "transform", "label": "东区", "config": {"filters": [{"field": "region", "operator": "=", "value": "East"}]}},
                            {"id": "west_orders", "type": "transform", "label": "西区", "config": {"filters": [{"field": "region", "operator": "=", "value": "West"}]}},
                            {"id": "union_orders", "type": "union", "label": "汇总分支", "config": {"mode": "distinct", "keys": ["order_id"]}},
                            {"id": "load_orders", "type": "load", "label": "写入分支结果", "config": {"target_table": "etl_union_orders"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "east_orders"},
                            {"source": "extract_orders", "target": "west_orders"},
                            {"source": "east_orders", "target": "union_orders"},
                            {"source": "west_orders", "target": "union_orders"},
                            {"source": "union_orders", "target": "load_orders"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 4)
            self.assertEqual(run.records_written, 3)
            self.assertEqual(run.node_logs_json["summary"]["final_row_count"], 3)
        finally:
            os.unlink(source_path)

    def test_pipeline_reuses_one_transform_for_multiple_outputs(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="多点输出复用管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {"id": "valid_orders", "type": "transform", "label": "有效订单", "config": {"filters": [{"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]}]}},
                            {"id": "load_bi", "type": "load", "label": "输出 BI", "config": {"target_table": "etl_bi_orders"}},
                            {"id": "load_ops", "type": "load", "label": "输出运营", "config": {"target_table": "etl_ops_orders"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "valid_orders"},
                            {"source": "valid_orders", "target": "load_bi"},
                            {"source": "valid_orders", "target": "load_ops"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_written, 6)
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                bi_count = conn.execute(text("SELECT COUNT(*) FROM etl_bi_orders")).scalar()
                ops_count = conn.execute(text("SELECT COUNT(*) FROM etl_ops_orders")).scalar()
            engine.dispose()
            self.assertEqual((bi_count, ops_count), (3, 3))
        finally:
            os.unlink(source_path)

    def test_pipeline_sql_operator_runs_over_upstream_rows(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="SQL 算子分析管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "sql_summary",
                                "type": "sql",
                                "label": "SQL 汇总",
                                "config": {
                                    "sql": "SELECT region AS area, SUM(amount - discount) AS net_amount_sum, COUNT(order_id) AS order_count FROM input WHERE status IN ('PAID','COMPLETE') GROUP BY region",
                                },
                            },
                            {"id": "load_summary", "type": "load", "label": "写入汇总", "config": {"target_table": "etl_sql_summary"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "sql_summary"},
                            {"source": "sql_summary", "target": "load_summary"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.node_logs_json["summary"]["final_columns"], ["area", "net_amount_sum", "order_count"])
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM etl_sql_summary ORDER BY area")).fetchall()]
            engine.dispose()
            self.assertEqual(
                rows,
                [
                    {"area": "East", "net_amount_sum": 180.0, "order_count": 2},
                    {"area": "West", "net_amount_sum": 180.0, "order_count": 1},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_pipeline_sql_pushdown_materializes_large_scale_result_without_load_node(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="SQL 下推规模计算管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {
                                "id": "sql_pushdown",
                                "type": "sql",
                                "label": "数据库侧汇总",
                                "config": {
                                    "execution_mode": "pushdown",
                                    "datasource_id": 101,
                                    "target_table": "etl_pushdown_region_summary",
                                    "sql": "SELECT region, SUM(amount) AS gross_amount FROM order_events GROUP BY region",
                                },
                            }
                        ],
                        "edges": [],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_written, 2)
            sql_log = run.node_logs_json["nodes"][0]
            self.assertEqual(sql_log["execution_mode"], "pushdown")
            self.assertEqual(sql_log["external_target"], "etl_pushdown_region_summary")
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM etl_pushdown_region_summary")).scalar()
            engine.dispose()
            self.assertEqual(count, 2)
        finally:
            os.unlink(source_path)

    def test_pipeline_reverse_etl_writes_rows_back_to_business_table(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="反向 ETL 回写管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {"id": "paid_orders", "type": "transform", "label": "已支付订单", "config": {"filters": [{"field": "status", "operator": "=", "value": "PAID"}]}},
                            {"id": "sync_crm", "type": "reverse_etl", "label": "回写 CRM", "config": {"target_type": "database", "datasource_id": 101, "target_table": "crm_paid_orders", "mode": "replace"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "paid_orders"},
                            {"source": "paid_orders", "target": "sync_crm"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_written, 2)
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT order_id, status FROM crm_paid_orders ORDER BY order_id")).fetchall()]
            engine.dispose()
            self.assertEqual(rows, [{"order_id": "O001", "status": "PAID"}, {"order_id": "O001", "status": "PAID"}])
        finally:
            os.unlink(source_path)

    def test_pipeline_preview_accepts_unsaved_dag_json_for_realtime_validation(self):
        from app.api.pipelines import create_pipeline, preview_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelinePreviewRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="实时预览管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {"id": "filter_orders", "type": "transform", "label": "筛选订单", "config": {"filters": [{"field": "region", "operator": "=", "value": "East"}]}},
                        ],
                        "edges": [{"source": "extract_orders", "target": "filter_orders"}],
                    },
                ),
                db=db,
                current_user=admin,
            )
            unsaved_dag = {
                "nodes": [
                    {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                    {"id": "filter_orders", "type": "transform", "label": "筛选订单", "config": {"filters": [{"field": "region", "operator": "=", "value": "West"}]}},
                ],
                "edges": [{"source": "extract_orders", "target": "filter_orders"}],
            }

            preview = preview_pipeline(
                pipeline.id,
                PipelinePreviewRequest(node_id="filter_orders", limit=10, dag_json=unsaved_dag),
                db=db,
                current_user=admin,
            )

            self.assertEqual(preview.row_count, 1)
            self.assertEqual(preview.rows[0]["region"], "West")
        finally:
            os.unlink(source_path)

    def test_pipeline_inspect_profiles_selected_node_without_persisting_output(self):
        from app.api.pipelines import create_pipeline, inspect_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineInspectRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="Inspect 节点画像管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "paid_orders",
                                "type": "transform",
                                "label": "已支付订单",
                                "config": {
                                    "filters": [{"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]}],
                                    "field_mapping": [{"source": "region", "target": "area"}],
                                },
                            },
                            {"id": "load_orders", "type": "load", "label": "写入结果", "config": {"target_table": "inspect_should_not_exist"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "paid_orders"},
                            {"source": "paid_orders", "target": "load_orders"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            inspected = inspect_pipeline(
                pipeline.id,
                PipelineInspectRequest(node_id="paid_orders", limit=10),
                db=db,
                current_user=admin,
            )

            self.assertEqual(inspected.node_id, "paid_orders")
            self.assertEqual(inspected.execution_mode, "in_memory")
            self.assertIn({"name": "area", "type": "string", "nullable": False}, inspected.schema)
            area_profile = next(item for item in inspected.profile if item["name"] == "area")
            self.assertEqual(area_profile["unique_count"], 2)
            self.assertEqual(area_profile["null_count"], 0)
            self.assertEqual(inspected.row_count, 3)
            self.assertEqual(db.query(DataPipelineRun).count(), 0)
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                target_exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='inspect_should_not_exist'")).first()
            engine.dispose()
            self.assertIsNone(target_exists)
        finally:
            os.unlink(source_path)

    def test_pipeline_reverse_etl_upserts_rows_with_field_mapping(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        engine = create_engine(f"sqlite:///{source_path}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE crm_paid_orders_upsert (
                      crm_order_id TEXT NOT NULL,
                      crm_status TEXT,
                      amount REAL,
                      discount REAL,
                      region TEXT,
                      updated_at TEXT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO crm_paid_orders_upsert (crm_order_id, crm_status, amount, discount, region, updated_at)
                    VALUES (:crm_order_id, :crm_status, :amount, :discount, :region, :updated_at)
                    """
                ),
                [
                    {"crm_order_id": "O001", "crm_status": "OLD", "amount": 1.0, "discount": 0.0, "region": "Legacy", "updated_at": "2026-04-01T00:00:00"},
                    {"crm_order_id": "O999", "crm_status": "KEEP", "amount": 9.0, "discount": 0.0, "region": "North", "updated_at": "2026-04-01T00:00:00"},
                ],
            )
        engine.dispose()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="反向 ETL 主键回写管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {"id": "paid_orders", "type": "transform", "label": "已支付订单", "config": {"filters": [{"field": "status", "operator": "=", "value": "PAID"}]}},
                            {
                                "id": "sync_crm",
                                "type": "reverse_etl",
                                "label": "回写 CRM",
                                "config": {
                                    "target_type": "database",
                                    "datasource_id": 101,
                                    "target_table": "crm_paid_orders_upsert",
                                    "mode": "upsert",
                                    "upsert_keys": ["crm_order_id"],
                                    "field_mapping": [
                                        {"source": "order_id", "target": "crm_order_id"},
                                        {"source": "status", "target": "crm_status"},
                                    ],
                                },
                            },
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "paid_orders"},
                            {"source": "paid_orders", "target": "sync_crm"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.node_logs_json["nodes"][-1]["execution_mode"], "reverse_etl")
            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT crm_order_id, crm_status, region FROM crm_paid_orders_upsert ORDER BY crm_order_id")).fetchall()]
            engine.dispose()
            self.assertEqual(
                rows,
                [
                    {"crm_order_id": "O001", "crm_status": "PAID", "region": "East"},
                    {"crm_order_id": "O999", "crm_status": "KEEP", "region": "North"},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_pipeline_validation_blocks_reverse_etl_upsert_without_keys(self):
        from app.api.pipelines import create_pipeline, validate_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="反向 ETL 缺少更新键",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "sync_crm",
                                "type": "reverse_etl",
                                "label": "回写 CRM",
                                "config": {
                                    "target_type": "database",
                                    "datasource_id": 101,
                                    "target_table": "crm_paid_orders",
                                    "mode": "upsert",
                                },
                            },
                        ],
                        "edges": [{"source": "extract_orders", "target": "sync_crm"}],
                    },
                ),
                db=db,
                current_user=admin,
            )

            validation = validate_pipeline(pipeline.id, db=db, current_user=admin)

            self.assertEqual(validation.status, "blocked")
            self.assertTrue(any(item.code == "missing_reverse_etl_upsert_keys" for item in validation.diagnostics))
        finally:
            os.unlink(source_path)

    def test_quality_gate_fail_fast_false_allows_downstream_load(self):
        from app.api.pipelines import create_pipeline, create_quality_rule, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest, QualityRuleCreate

        source_path = self._source_database(
            [
                {"work_date": "2026-05-01", "line": "A", "oee": 91.5, "revenue": 12000},
                {"work_date": "2026-05-02", "line": "B", "oee": None, "revenue": 9800},
            ]
        )
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="质量失败不中断管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract", "type": "extract", "label": "抽取"},
                            {"id": "quality", "type": "quality", "label": "质量闸门", "config": {"fail_fast": False}},
                            {"id": "load", "type": "load", "label": "装载", "config": {"target_table": "quality_non_blocking", "batch_size": 1}},
                        ],
                        "edges": [
                            {"source": "extract", "target": "quality"},
                            {"source": "quality", "target": "load"},
                        ],
                    },
                ),
                db=db,
                current_user=admin,
            )
            create_quality_rule(
                QualityRuleCreate(
                    pipeline_id=pipeline.id,
                    dataset_id=301,
                    name="OEE 必填",
                    rule_type="not_null",
                    field="oee",
                    severity="error",
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_failed, 1)
            self.assertEqual(run.records_written, 2)
            self.assertEqual(run.node_logs_json["summary"]["quality"], "failed")
            quality_log = next(node for node in run.node_logs_json["nodes"] if node["node_id"] == "quality")
            load_log = next(node for node in run.node_logs_json["nodes"] if node["node_id"] == "load")
            self.assertEqual(quality_log["status"], "warning")
            self.assertEqual(load_log["status"], "success")
            self.assertEqual(load_log["batch_size"], 1)
            self.assertEqual(load_log["batch_count"], 2)
        finally:
            os.unlink(source_path)

    def test_metadata_extract_node_refreshes_datasource_schema_metadata(self):
        import json

        from app.api.pipelines import create_pipeline, preview_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelinePreviewRequest, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

            pipeline = create_pipeline(
                PipelineCreate(
                    name="元数据抽取管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {
                                "id": "extract_metadata",
                                "type": "metadata_extract",
                                "label": "抽取元数据",
                                "config": {"datasource_id": 101, "tables": ["order_events"], "refresh_schema": True},
                            },
                            {"id": "load_metadata", "type": "load", "label": "写入元数据快照", "config": {"target_table": "etl_metadata_snapshot"}},
                        ],
                        "edges": [{"source": "extract_metadata", "target": "load_metadata"}],
                    },
                ),
                db=db,
                current_user=admin,
            )

            preview = preview_pipeline(
                pipeline.id,
                PipelinePreviewRequest(node_id="extract_metadata", limit=20),
                db=db,
                current_user=admin,
            )
            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)
            datasource = db.query(DataSource).filter(DataSource.id == 101).one()
            metadata = json.loads(datasource.schema_metadata)

            self.assertEqual(preview.row_count, 6)
            self.assertEqual(run.status, "success")
            self.assertEqual(metadata["tables"][0]["name"], "order_events")
            self.assertIn("updated_at", [column["name"] for column in metadata["tables"][0]["columns"]])
        finally:
            os.unlink(source_path)

    def test_metadata_extract_node_syncs_tables_to_catalog_when_enabled(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    DataAsset.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="元数据同步目录管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {
                                "id": "extract_metadata",
                                "type": "metadata_extract",
                                "label": "抽取元数据",
                                "config": {
                                    "datasource_id": 101,
                                    "tables": ["order_events"],
                                    "refresh_schema": True,
                                    "write_to_catalog": True,
                                },
                            },
                            {"id": "load_metadata", "type": "load", "label": "写入元数据快照", "config": {"target_table": "etl_metadata_snapshot"}},
                        ],
                        "edges": [{"source": "extract_metadata", "target": "load_metadata"}],
                    },
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(pipeline.id, PipelineRunRequest(mode="manual"), db=db, current_user=admin)

            asset = db.query(DataAsset).filter(DataAsset.asset_type == "table", DataAsset.datasource_id == 101, DataAsset.name == "order_events").one()
            self.assertEqual(run.status, "success")
            self.assertEqual(asset.status, "published")
            self.assertEqual(asset.org_id, 1)
            self.assertEqual(asset.owner_id, 10)
            self.assertEqual(asset.metadata_json["source"], "metadata_extract")
            self.assertEqual(asset.metadata_json["pipeline_id"], pipeline.id)
            self.assertIn("updated_at", [column["name"] for column in asset.metadata_json["columns"]])
        finally:
            os.unlink(source_path)

    def test_pipeline_publish_versions_capture_dag_snapshot(self):
        from app.api.pipelines import create_pipeline, list_pipeline_versions, publish_pipeline_version
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataPipelineVersion, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineVersion.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="版本化加工管道",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取"},
                            {"id": "load_orders", "type": "load", "label": "写入"},
                        ],
                        "edges": [{"source": "extract_orders", "target": "load_orders"}],
                    },
                ),
                db=db,
                current_user=admin,
            )

            version = publish_pipeline_version(pipeline.id, db=db, current_user=admin)
            versions = list_pipeline_versions(pipeline.id, db=db, current_user=admin)

            db.refresh(pipeline)
            self.assertEqual(version.version, 1)
            self.assertEqual(version.status, "published")
            self.assertEqual(pipeline.current_version, 1)
            self.assertEqual(pipeline.published_version, 1)
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].dag_json["nodes"][0]["id"], "extract_orders")
        finally:
            os.unlink(source_path)

    def test_pipeline_preview_rejects_unknown_node_id(self):
        from fastapi import HTTPException

        from app.api.pipelines import create_pipeline, preview_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelinePreviewRequest

        source_path = self._source_database(
            [
                {"work_date": "2026-05-01", "line": "A", "oee": 91.5, "revenue": 12000},
            ]
        )
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._pipeline_payload(), db=db, current_user=admin)

            with self.assertRaises(HTTPException) as error:
                preview_pipeline(
                    pipeline.id,
                    PipelinePreviewRequest(node_id="missing_node", limit=10),
                    db=db,
                    current_user=admin,
                )

            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("预览节点不存在", error.exception.detail)
        finally:
            os.unlink(source_path)

    def test_pipeline_validation_warns_when_quality_gate_has_no_active_rules(self):
        from app.api.pipelines import create_pipeline, validate_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        source_path = self._source_database(
            [
                {"work_date": "2026-05-01", "line": "A", "oee": 91.5, "revenue": 12000},
            ]
        )
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_pipeline_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            pipeline = create_pipeline(self._pipeline_payload(), db=db, current_user=admin)

            validation = validate_pipeline(pipeline.id, db=db, current_user=admin)

            self.assertEqual(validation.status, "warning")
            self.assertEqual(validation.critical_count, 0)
            self.assertTrue(any(item.code == "missing_quality_rules" for item in validation.diagnostics))
        finally:
            os.unlink(source_path)

    def test_zero_to_one_pipeline_lifecycle_uses_real_creation_apis(self):
        from app.api.datasource import create_datasource
        from app.api.datasets import create_dataset
        from app.api.pipelines import (
            create_pipeline,
            create_quality_rule,
            get_pipeline_lineage,
            preview_pipeline,
            run_pipeline,
            validate_pipeline,
        )
        from app.models.audit_log import AuditLog
        from app.models.catalog import AssetLineage, DataAsset
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.datasource import DataSourceCreate
        from app.schemas.dataset import DatasetCreate
        from app.schemas.pipeline import PipelineCreate, PipelinePreviewRequest, PipelineRunRequest, QualityRuleCreate

        source_path = self._order_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                    DataAsset.__table__,
                    AssetLineage.__table__,
                ]
            )
            db.add_all(
                [
                    Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                    User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                ]
            )
            db.commit()
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

            datasource = create_datasource(
                DataSourceCreate(
                    name="Zero One ERP",
                    slug="zero-one-erp",
                    source_type="database",
                    database_url=f"sqlite:///{source_path}",
                    metadata_prompt="订单事实表 order_events，可用于企业经营分析。",
                ),
                db=db,
                current_user=admin,
            )
            dataset = create_dataset(
                DatasetCreate(
                    name="Zero One Orders",
                    datasource_id=datasource["id"],
                    fields_json={
                        "table": "order_events",
                        "fields": [
                            "order_events.order_id",
                            "order_events.status",
                            "order_events.amount",
                            "order_events.discount",
                            "order_events.region",
                        ],
                    },
                    status="published",
                    visibility="org",
                ),
                db=db,
                current_user=admin,
            )
            pipeline = create_pipeline(
                PipelineCreate(
                    name="Zero One 订单加工管道",
                    dataset_id=dataset.id,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "transform_orders",
                                "type": "transform",
                                "label": "清洗聚合订单",
                                "config": {
                                    "field_mapping": [{"source": "region", "target": "area"}],
                                    "type_conversions": [
                                        {"field": "amount", "type": "decimal"},
                                        {"field": "discount", "type": "decimal"},
                                    ],
                                    "filters": [{"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]}],
                                    "derived_columns": [{"name": "net_amount", "expression": "amount - discount"}],
                                    "dedupe": {"keys": ["order_id"], "keep": "first"},
                                    "aggregations": {
                                        "group_by": ["area"],
                                        "metrics": [
                                            {"field": "net_amount", "function": "sum", "alias": "net_amount_sum"},
                                            {"field": "order_id", "function": "count", "alias": "order_count"},
                                        ],
                                    },
                                },
                            },
                            {"id": "quality_gate", "type": "quality", "label": "质量闸门"},
                            {
                                "id": "load_summary",
                                "type": "load",
                                "label": "写入订单汇总",
                                "config": {"target_table": "zero_one_order_summary", "mode": "replace"},
                            },
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "transform_orders"},
                            {"source": "transform_orders", "target": "quality_gate"},
                            {"source": "quality_gate", "target": "load_summary"},
                        ],
                    },
                    run_mode="scheduled",
                    schedule_cron="0 2 * * *",
                    environment="prod",
                    priority="high",
                    alert_policy_json={"channels": ["wechat_work"], "on_failure": True},
                ),
                db=db,
                current_user=admin,
            )
            create_quality_rule(
                QualityRuleCreate(
                    pipeline_id=pipeline.id,
                    dataset_id=dataset.id,
                    name="汇总行数至少 2 行",
                    rule_type="row_count",
                    operator="gte",
                    threshold="2",
                    severity="error",
                ),
                db=db,
                current_user=admin,
            )

            validation = validate_pipeline(pipeline.id, db=db, current_user=admin)
            preview = preview_pipeline(
                pipeline.id,
                PipelinePreviewRequest(node_id="transform_orders", limit=10),
                db=db,
                current_user=admin,
            )
            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="zero-to-one integration test"),
                db=db,
                current_user=admin,
            )
            lineage = get_pipeline_lineage(pipeline.id, db=db, current_user=admin)

            self.assertEqual(validation.status, "ready")
            self.assertEqual(preview.columns, ["area", "net_amount_sum", "order_count"])
            self.assertEqual(preview.row_count, 2)
            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 4)
            self.assertEqual(run.records_written, 2)
            self.assertEqual(run.node_logs_json["summary"]["quality"], "passed")
            self.assertEqual(lineage.source["table"], "order_events")
            self.assertEqual(lineage.target["target_tables"], ["zero_one_order_summary"])

            db.refresh(dataset)
            self.assertEqual(dataset.last_refresh_status, "success")
            self.assertEqual(dataset.last_refresh_row_count, 2)
            self.assertEqual(db.query(DataPipelineRun).filter(DataPipelineRun.pipeline_id == pipeline.id).count(), 1)

            engine = create_engine(f"sqlite:///{source_path}")
            with engine.connect() as conn:
                rows = [dict(row._mapping) for row in conn.execute(text("SELECT * FROM zero_one_order_summary ORDER BY area")).fetchall()]
            engine.dispose()
            self.assertEqual(
                rows,
                [
                    {"area": "East", "net_amount_sum": 90.0, "order_count": 1},
                    {"area": "West", "net_amount_sum": 180.0, "order_count": 1},
                ],
            )
        finally:
            os.unlink(source_path)

    def test_excel_source_pipeline_load_writes_managed_target_table(self):
        from app.api.datasource import create_datasource
        from app.api.datasets import create_dataset
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.datasource import DataSourceCreate
        from app.schemas.dataset import DatasetCreate
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._excel_order_source_file()
        target_path = Path(source_path).with_name(f"{Path(source_path).stem}.etl.sqlite")
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            db.add_all(
                [
                    Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                    User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                ]
            )
            db.commit()
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)

            datasource = create_datasource(
                DataSourceCreate(
                    name="Excel Sales",
                    slug="excel-sales",
                    source_type="excel",
                    database_url=source_path,
                    metadata_prompt="订单主表 orders",
                ),
                db=db,
                current_user=admin,
            )
            dataset = create_dataset(
                DatasetCreate(
                    name="Excel Orders",
                    datasource_id=datasource["id"],
                    fields_json={
                        "table": "orders",
                        "fields": [
                            "orders.order_id",
                            "orders.order_date",
                            "orders.status",
                            "orders.total_amount",
                        ],
                    },
                    status="published",
                    visibility="org",
                ),
                db=db,
                current_user=admin,
            )
            pipeline = create_pipeline(
                PipelineCreate(
                    name="Excel 订单落表",
                    dataset_id=dataset.id,
                    dag_json={
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "normalize_orders",
                                "type": "transform",
                                "label": "标准化日期",
                                "config": {"type_conversions": [{"field": "order_date", "type": "datetime"}]},
                            },
                            {
                                "id": "load_orders",
                                "type": "load",
                                "label": "写入订单目标表",
                                "config": {
                                    "target_table": "etl_excel_orders",
                                    "mode": "upsert",
                                    "primary_key": "order_id",
                                    "upsert_keys": ["order_id"],
                                },
                            },
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "normalize_orders"},
                            {"source": "normalize_orders", "target": "load_orders"},
                        ],
                    },
                    run_mode="manual",
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="manual", reason="excel target integration test"),
                db=db,
                current_user=admin,
            )

            self.assertEqual(run.status, "success")
            self.assertEqual(run.records_read, 2)
            self.assertEqual(run.records_written, 2)
            self.assertTrue(target_path.exists())
            load_log = next(node for node in run.node_logs_json["nodes"] if node["node_id"] == "load_orders")
            self.assertEqual(load_log["external_target"], "etl_excel_orders")
            self.assertEqual(load_log["target_store"], "managed_sqlite")
            transform_log = next(node for node in run.node_logs_json["nodes"] if node["node_id"] == "normalize_orders")
            self.assertEqual(transform_log["preview"][0]["order_date"], "2026-05-14T00:00:00")

            target_engine = create_engine(f"sqlite:///{target_path}")
            try:
                with target_engine.connect() as conn:
                    rows = [
                        dict(row._mapping)
                        for row in conn.execute(text("SELECT order_id, total_amount FROM etl_excel_orders ORDER BY order_id")).fetchall()
                    ]
            finally:
                target_engine.dispose()
            self.assertEqual(rows, [{"order_id": "ORD001", "total_amount": 1200}, {"order_id": "ORD002", "total_amount": 800}])

            db.refresh(dataset)
            self.assertEqual(dataset.materialization_status, "ready")
            self.assertEqual(dataset.materialization_mode, "pipeline")
            self.assertEqual(dataset.materialized_table_name, "etl_excel_orders")
        finally:
            os.unlink(source_path)
            if target_path.exists():
                target_path.unlink()

    def test_failed_incremental_run_does_not_advance_dataset_watermark(self):
        from app.api.pipelines import create_pipeline, run_pipeline
        from app.models.audit_log import AuditLog
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User
        from app.schemas.pipeline import PipelineCreate, PipelineRunRequest

        source_path = self._multi_source_database()
        try:
            db = self._db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                ]
            )
            self._seed_multi_dataset_fixture(db, source_path)
            admin = SimpleNamespace(id=10, username="nova.admin", role="org_admin", org_id=1)
            dataset = db.get(Dataset, 301)
            pipeline = create_pipeline(
                PipelineCreate(
                    name="失败的增量订单同步",
                    dataset_id=301,
                    dag_json={
                        "nodes": [
                            {
                                "id": "extract_orders",
                                "type": "extract",
                                "label": "抽取订单",
                                "config": {"mode": "incremental", "incremental_key": "updated_at"},
                            },
                            {
                                "id": "load_orders",
                                "type": "load",
                                "label": "写入失败",
                                "config": {"target_table": "etl_failed_orders", "mode": "merge"},
                            },
                        ],
                        "edges": [{"source": "extract_orders", "target": "load_orders"}],
                    },
                    run_mode="incremental",
                ),
                db=db,
                current_user=admin,
            )

            run = run_pipeline(
                pipeline.id,
                PipelineRunRequest(mode="incremental", reason="expected load failure"),
                db=db,
                current_user=admin,
            )

            self.assertEqual(run.status, "failed")
            db.refresh(dataset)
            self.assertIsNone(dataset.incremental_key)
            self.assertIsNone(dataset.incremental_watermark)
        finally:
            os.unlink(source_path)

    def test_zero_to_one_pipeline_http_api_smoke(self):
        from app.api.auth import get_current_user
        from app.api.routes import api_router
        from app.db.session import get_db
        from app.models.audit_log import AuditLog
        from app.models.catalog import AssetLineage, DataAsset
        from app.models.data_pipeline import DataPipeline, DataPipelineRun, DataQualityRule
        from app.models.dataset import Dataset, DatasetRefreshLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        source_path = self._order_source_database()
        try:
            db = self._http_db(
                [
                    Organization.__table__,
                    User.__table__,
                    DataSource.__table__,
                    Dataset.__table__,
                    DatasetRefreshLog.__table__,
                    DataPipeline.__table__,
                    DataPipelineRun.__table__,
                    DataQualityRule.__table__,
                    AuditLog.__table__,
                    DataAsset.__table__,
                    AssetLineage.__table__,
                ]
            )
            db.add_all(
                [
                    Organization(id=1, name="Nova Manufacturing", slug="nova-mfg"),
                    User(id=10, username="nova.admin", hashed_password="x", role="org_admin", org_id=1),
                ]
            )
            db.commit()
            admin = db.query(User).filter(User.id == 10).one()

            app = FastAPI()
            app.include_router(api_router, prefix="/api")

            def override_db():
                yield db

            app.dependency_overrides[get_db] = override_db
            app.dependency_overrides[get_current_user] = lambda: admin
            client = TestClient(app)

            datasource_resp = client.post(
                "/api/datasources",
                json={
                    "name": "HTTP Zero One ERP",
                    "slug": "http-zero-one-erp",
                    "source_type": "database",
                    "database_url": f"sqlite:///{source_path}",
                    "metadata_prompt": "订单事实表 order_events",
                },
            )
            self.assertEqual(datasource_resp.status_code, 200, datasource_resp.text)
            datasource_id = datasource_resp.json()["id"]

            dataset_resp = client.post(
                "/api/datasets",
                json={
                    "name": "HTTP Zero One Orders",
                    "datasource_id": datasource_id,
                    "fields_json": {
                        "table": "order_events",
                        "fields": [
                            "order_events.order_id",
                            "order_events.status",
                            "order_events.amount",
                            "order_events.discount",
                            "order_events.region",
                        ],
                    },
                    "status": "published",
                    "visibility": "org",
                },
            )
            self.assertEqual(dataset_resp.status_code, 200, dataset_resp.text)
            dataset_id = dataset_resp.json()["id"]

            pipeline_resp = client.post(
                "/api/pipelines",
                json={
                    "name": "HTTP Zero One 订单加工管道",
                    "dataset_id": dataset_id,
                    "dag_json": {
                        "nodes": [
                            {"id": "extract_orders", "type": "extract", "label": "抽取订单"},
                            {
                                "id": "transform_orders",
                                "type": "transform",
                                "label": "清洗聚合订单",
                                "config": {
                                    "field_mapping": [{"source": "region", "target": "area"}],
                                    "filters": [{"field": "status", "operator": "in", "value": ["PAID", "COMPLETE"]}],
                                    "derived_columns": [{"name": "net_amount", "expression": "amount - discount"}],
                                    "dedupe": {"keys": ["order_id"], "keep": "first"},
                                    "aggregations": {
                                        "group_by": ["area"],
                                        "metrics": [
                                            {"field": "net_amount", "function": "sum", "alias": "net_amount_sum"},
                                            {"field": "order_id", "function": "count", "alias": "order_count"},
                                        ],
                                    },
                                },
                            },
                            {"id": "quality_gate", "type": "quality", "label": "质量闸门"},
                            {"id": "load_summary", "type": "load", "label": "写入订单汇总", "config": {"target_table": "http_zero_one_order_summary"}},
                        ],
                        "edges": [
                            {"source": "extract_orders", "target": "transform_orders"},
                            {"source": "transform_orders", "target": "quality_gate"},
                            {"source": "quality_gate", "target": "load_summary"},
                        ],
                    },
                    "run_mode": "manual",
                    "environment": "prod",
                    "priority": "high",
                    "alert_policy_json": {"channels": ["wechat_work"], "on_failure": True},
                },
            )
            self.assertEqual(pipeline_resp.status_code, 200, pipeline_resp.text)
            pipeline_id = pipeline_resp.json()["id"]

            rule_resp = client.post(
                "/api/quality-rules",
                json={
                    "pipeline_id": pipeline_id,
                    "dataset_id": dataset_id,
                    "name": "汇总行数至少 2 行",
                    "rule_type": "row_count",
                    "operator": "gte",
                    "threshold": "2",
                    "severity": "error",
                },
            )
            self.assertEqual(rule_resp.status_code, 200, rule_resp.text)

            validate_resp = client.post(f"/api/pipelines/{pipeline_id}/validate")
            preview_resp = client.post(f"/api/pipelines/{pipeline_id}/preview", json={"node_id": "transform_orders", "limit": 10})
            run_resp = client.post(f"/api/pipelines/{pipeline_id}/run", json={"mode": "manual", "reason": "http smoke"})
            lineage_resp = client.get(f"/api/pipelines/{pipeline_id}/lineage")

            self.assertEqual(validate_resp.status_code, 200, validate_resp.text)
            self.assertEqual(preview_resp.status_code, 200, preview_resp.text)
            self.assertEqual(run_resp.status_code, 200, run_resp.text)
            self.assertEqual(lineage_resp.status_code, 200, lineage_resp.text)
            self.assertEqual(validate_resp.json()["status"], "ready")
            self.assertEqual(preview_resp.json()["columns"], ["area", "net_amount_sum", "order_count"])
            self.assertEqual(run_resp.json()["status"], "success")
            self.assertEqual(run_resp.json()["records_written"], 2)
            self.assertEqual(lineage_resp.json()["target"]["target_tables"], ["http_zero_one_order_summary"])
        finally:
            os.unlink(source_path)
