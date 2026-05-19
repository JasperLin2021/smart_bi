import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class MetricFromQueryTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _seed_agentic_history(self, db, *, with_dataset=True):
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.query import QueryHistory

        datasource = DataSource(
            name="alarm_detail",
            slug="alarm-detail",
            source_type="excel",
            database_url="/tmp/alarm.xlsx",
            metadata_prompt="sheet1(ALARMID,EQUIPMENTID,SUMDATETIME)",
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = None
        if with_dataset:
            dataset = Dataset(
                name="alarm_detail 基础数据集",
                datasource_id=datasource.id,
                fields_json={"table": "sheet1"},
                status="published",
                visibility="org",
                org_id=2,
                owner_id=9,
            )
            db.add(dataset)
            db.flush()

        result = {
            "columns": ["ALARMID", "EQUIPMENTID", "trend_date", "occurrence_count"],
            "rows": [
                {"ALARMID": "A01", "EQUIPMENTID": "EQ1", "trend_date": "2026-05-01", "occurrence_count": 12},
                {"ALARMID": "A01", "EQUIPMENTID": "EQ2", "trend_date": "2026-05-01", "occurrence_count": 8},
            ],
            "_chart_spec": {
                "chart_type": "line",
                "x_field": "trend_date",
                "y_field": "occurrence_count",
                "series_fields": ["EQUIPMENTID"],
                "facet_field": "ALARMID",
            },
            "_agent_trace": [{"stage": "execute", "status": "success", "message": "ok"}],
        }
        history = QueryHistory(
            user_id=9,
            datasource_id=datasource.id,
            question="[探索模式] TOP3 的 alarmcode 中发生次数最多的设备的趋势图，也取 TOP10",
            sql_query=(
                "SELECT ALARMID, EQUIPMENTID, CAST(SUMDATETIME AS DATE) AS trend_date, "
                "COUNT(*) AS occurrence_count FROM sheet1 GROUP BY ALARMID, EQUIPMENTID, CAST(SUMDATETIME AS DATE)"
            ),
            result_json=json.dumps(result, ensure_ascii=False),
            summary="ok",
            mode="agentic",
            llm_model="deepseek-v4-flash",
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return datasource, history, dataset

    def test_metric_draft_from_query_uses_llm_candidate_and_marks_topn_as_analysis_condition(self):
        from app.api.metrics import draft_metric_from_query
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.query import QueryHistory
        from app.schemas.metric import MetricFromQueryDraftRequest

        db = self._db([DataSource.__table__, Dataset.__table__, QueryHistory.__table__, Metric.__table__])
        _datasource, history, dataset = self._seed_agentic_history(db)

        async def fake_chat_completion(*_args, **_kwargs):
            return json.dumps(
                {
                    "name": "报警发生次数",
                    "definition": "统计报警明细记录的发生次数",
                    "formula": "COUNT(*)",
                    "unit": "次",
                    "metric_column": "occurrence_count",
                    "dimensions": ["ALARMID", "EQUIPMENTID"],
                    "time_column": "trend_date",
                    "warnings": ["TOP3、TOP10 属于分析条件，不写入指标公式"],
                },
                ensure_ascii=False,
            )

        with patch("app.api.metrics.chat_completion", new=fake_chat_completion):
            response = asyncio.run(
                draft_metric_from_query(
                    MetricFromQueryDraftRequest(query_history_id=history.id),
                    db=db,
                    current_user=SimpleNamespace(id=9, username="dept", role="dept_admin", org_id=2),
                )
            )

        self.assertEqual(response["candidate"]["name"], "报警发生次数")
        self.assertEqual(response["candidate"]["formula"], "COUNT(*)")
        self.assertEqual(response["candidate"]["metric_column"], "occurrence_count")
        self.assertEqual(response["candidate"]["dimensions"], ["ALARMID", "EQUIPMENTID"])
        self.assertEqual(response["candidate"]["time_column"], "trend_date")
        self.assertTrue(response["llm_enhanced"])
        self.assertIn("分析条件", " ".join(response["warnings"]))
        self.assertEqual(response["source"]["source_type"], "agentic_query")
        self.assertEqual(response["source"]["source_query_history_id"], history.id)
        self.assertEqual(response["source"]["source_dataset_id"], dataset.id)
        self.assertEqual(response["source"]["source_dataset_name"], dataset.name)

    def test_create_metric_from_query_persists_draft_with_agentic_lineage(self):
        from app.api.metrics import create_metric_from_query
        from app.models.audit_log import AuditLog
        from app.models.catalog import DataAsset
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.query import QueryHistory
        from app.schemas.metric import MetricFromQueryCreateRequest

        db = self._db([DataSource.__table__, Dataset.__table__, QueryHistory.__table__, Metric.__table__, DataAsset.__table__, AuditLog.__table__])
        datasource, history, dataset = self._seed_agentic_history(db)

        with patch("app.api.metrics.sync_datasource_metrics_prompt"):
            metric = asyncio.run(
                create_metric_from_query(
                    MetricFromQueryCreateRequest(
                        query_history_id=history.id,
                        name="报警发生次数",
                        definition="统计报警明细记录的发生次数",
                        formula="COUNT(*)",
                        unit="次",
                        selected_metric_column="occurrence_count",
                        selected_dimensions=["ALARMID", "EQUIPMENTID"],
                        time_column="trend_date",
                    ),
                    db=db,
                    current_user=SimpleNamespace(id=9, username="dept", role="dept_admin", org_id=2),
                )
            )

        self.assertIsInstance(metric, Metric)
        self.assertEqual(metric.datasource_id, datasource.id)
        self.assertEqual(metric.dataset_id, dataset.id)
        self.assertEqual(metric.status, "draft")
        self.assertEqual(metric.certification_status, "pending_review")
        self.assertEqual(metric.quality_status, "unknown")
        self.assertEqual(metric.dimensions, ["ALARMID", "EQUIPMENTID"])
        self.assertEqual(metric.calculation_config["source"]["source_type"], "agentic_query")
        self.assertEqual(metric.calculation_config["source"]["source_query_history_id"], history.id)
        self.assertEqual(metric.calculation_config["source"]["source_dataset_id"], dataset.id)
        self.assertEqual(metric.calculation_config["source"]["source_metric_column"], "occurrence_count")
        self.assertEqual(metric.calculation_config["time_field"], "trend_date")

    def test_metric_from_query_requires_same_datasource_dataset(self):
        from fastapi import HTTPException

        from app.api.metrics import draft_metric_from_query
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.query import QueryHistory
        from app.schemas.metric import MetricFromQueryDraftRequest

        db = self._db([DataSource.__table__, Dataset.__table__, QueryHistory.__table__, Metric.__table__])
        _datasource, history, _dataset = self._seed_agentic_history(db, with_dataset=False)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                draft_metric_from_query(
                    MetricFromQueryDraftRequest(query_history_id=history.id),
                    db=db,
                    current_user=SimpleNamespace(id=9, username="dept", role="dept_admin", org_id=2),
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("请先创建基础数据集", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
