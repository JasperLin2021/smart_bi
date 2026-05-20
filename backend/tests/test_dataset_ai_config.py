import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DatasetAiConfigTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def _fixture(self):
        from app.models.audit_log import AuditLog
        from app.models.dataset import Dataset
        from app.models.datasource import DataSource

        db = self._db([DataSource.__table__, Dataset.__table__, AuditLog.__table__])
        datasource = DataSource(
            name="Alarm Detail",
            slug="alarm-detail",
            source_type="excel",
            database_url="sqlite:///:memory:",
            metadata_prompt="alarm detail metadata",
            schema_metadata=json.dumps(
                {
                    "tables": [
                        {
                            "name": "sheet1",
                            "description": "报警明细",
                            "columns": [
                                {"name": "ALARMID", "type": "VARCHAR", "description": "报警码"},
                                {"name": "EQUIPMENTID", "type": "VARCHAR", "description": "设备"},
                                {"name": "SUMDATETIME", "type": "DATETIME", "description": "发生时间"},
                                {"name": "TOTALTIMES", "type": "INTEGER", "description": "发生次数"},
                            ],
                        }
                    ],
                    "relationships": [],
                },
                ensure_ascii=False,
            ),
            org_id=2,
        )
        db.add(datasource)
        db.flush()
        dataset = Dataset(
            name="Alarm Dataset",
            datasource_id=datasource.id,
            fields_json={
                "table": "sheet1",
                "dimensions": [{"field": "sheet1.ALARMID", "alias": "报警码"}],
                "metrics": [{"field": "sheet1.TOTALTIMES", "aggregation": "SUM", "alias": "发生次数"}],
            },
            semantic_model_json={
                "dimensions": [{"id": "alarmid", "field": "sheet1.ALARMID", "label": "报警码"}],
                "metrics": [{"id": "total_times", "field": "sheet1.TOTALTIMES", "label": "发生次数", "aggregation": "sum"}],
                "time_dimensions": [],
                "synonyms": [],
            },
            status="published",
            visibility="org",
            org_id=2,
            owner_id=10,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return db, datasource, dataset

    def test_dataset_drill_config_round_trip_on_update(self):
        from app.api.datasets import update_dataset
        from app.models.dataset import Dataset
        from app.schemas.dataset import DatasetUpdate

        db, _, dataset = self._fixture()
        drill_config = {
            "dimensions": [
                {
                    "id": "alarmid",
                    "table": "sheet1",
                    "column": "ALARMID",
                    "label": "报警码",
                    "kind": "alarm",
                    "enabled": True,
                },
                {
                    "id": "equipmentid",
                    "table": "sheet1",
                    "column": "EQUIPMENTID",
                    "label": "设备",
                    "kind": "equipment",
                    "enabled": True,
                },
            ],
            "metrics": [],
            "paths": [
                {
                    "id": "alarmid__equipmentid",
                    "source_dimension_id": "alarmid",
                    "target_dimension_id": "equipmentid",
                    "label": "看设备分布",
                    "action": "group_by",
                    "enabled": True,
                }
            ],
        }

        response = update_dataset(
            dataset.id,
            DatasetUpdate(drill_config_json=drill_config),
            db=db,
            current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
        )

        self.assertEqual(response.drill_config_json["paths"][0]["label"], "看设备分布")
        self.assertEqual(db.query(Dataset).one().drill_config_json["dimensions"][1]["column"], "EQUIPMENTID")

    def test_ai_config_suggest_uses_llm_json_and_normalizes_result(self):
        from app.api.datasets import suggest_dataset_ai_config
        from app.schemas.dataset import DatasetAIConfigSuggestRequest

        db, datasource, _ = self._fixture()

        async def fake_chat_completion(*_args, **_kwargs):
            return json.dumps(
                {
                    "semantic_model": {
                        "dimensions": [
                            {"id": "alarmid", "field": "sheet1.ALARMID", "label": "报警码"},
                            {"id": "equipmentid", "field": "sheet1.EQUIPMENTID", "label": "设备"},
                        ],
                        "metrics": [
                            {"id": "alarm_count", "field": "*", "label": "报警发生次数", "aggregation": "count"}
                        ],
                        "time_dimensions": [
                            {"id": "sumdatetime", "field": "sheet1.SUMDATETIME", "label": "日期", "granularity": "day"}
                        ],
                        "synonyms": [],
                    },
                    "drill_config": {
                        "dimensions": [
                            {
                                "id": "alarmid",
                                "table": "sheet1",
                                "column": "ALARMID",
                                "label": "报警码",
                                "kind": "alarm",
                                "enabled": True,
                            },
                            {
                                "id": "equipmentid",
                                "table": "sheet1",
                                "column": "EQUIPMENTID",
                                "label": "设备",
                                "kind": "equipment",
                                "enabled": True,
                            },
                        ],
                        "metrics": [],
                        "paths": [
                            {
                                "id": "alarmid__equipmentid",
                                "source_dimension_id": "alarmid",
                                "target_dimension_id": "equipmentid",
                                "label": "看设备分布",
                                "action": "group_by",
                                "enabled": True,
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            )

        with patch("app.core.dataset_ai_config.chat_completion", new=fake_chat_completion):
            response = asyncio.run(
                suggest_dataset_ai_config(
                    DatasetAIConfigSuggestRequest(datasource_id=datasource.id, table="sheet1"),
                    db=db,
                    current_user=SimpleNamespace(id=10, username="owner", role="user", org_id=2),
                )
            )

        self.assertEqual(response["semantic_model"]["metrics"][0]["id"], "alarm_count")
        self.assertEqual(response["drill_config"]["paths"][0]["id"], "alarmid__equipmentid")
        self.assertEqual(response["field_roles"][0]["role"], "dimension")

    def test_drill_preview_prefers_dataset_drill_config(self):
        from app.api.query import drill_preview
        from app.schemas.query import DrillPreviewRequest

        db, datasource, dataset = self._fixture()
        dataset.drill_config_json = {
            "dimensions": [
                {
                    "id": "alarmid",
                    "table": "sheet1",
                    "column": "ALARMID",
                    "label": "报警码",
                    "kind": "alarm",
                    "enabled": True,
                },
                {
                    "id": "equipmentid",
                    "table": "sheet1",
                    "column": "EQUIPMENTID",
                    "label": "设备",
                    "kind": "equipment",
                    "enabled": True,
                },
            ],
            "metrics": [],
            "paths": [
                {
                    "id": "alarmid__equipmentid",
                    "source_dimension_id": "alarmid",
                    "target_dimension_id": "equipmentid",
                    "label": "看设备分布",
                    "action": "group_by",
                    "enabled": True,
                }
            ],
        }
        db.commit()

        response = asyncio.run(
            drill_preview(
                DrillPreviewRequest(
                    datasource_id=datasource.id,
                    dataset_id=dataset.id,
                    question="报警码下钻",
                    sql_query="SELECT ALARMID, SUM(TOTALTIMES) AS total_times FROM sheet1 GROUP BY ALARMID",
                    selected_column="ALARMID",
                    columns=["ALARMID", "total_times"],
                    row={"ALARMID": "A01", "total_times": 10},
                ),
                db=db,
                current_user=SimpleNamespace(id=99, username="analyst", role="user", org_id=2),
            )
        )

        self.assertEqual(response["actions"][0]["label"], "看设备分布")
        self.assertEqual(response["actions"][0]["source_value"], "A01")


if __name__ == "__main__":
    unittest.main()
