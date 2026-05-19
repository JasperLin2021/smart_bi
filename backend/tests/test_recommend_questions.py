import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.datasource import ColumnSchema, SchemaMetadata, TableSchema


class RecommendQuestionGenerationTests(unittest.TestCase):
    def _schema(self) -> SchemaMetadata:
        return SchemaMetadata(
            tables=[
                TableSchema(
                    name="alarm_detail",
                    description="报警明细",
                    columns=[
                        ColumnSchema(name="ALARMID", type="VARCHAR", description="报警码"),
                        ColumnSchema(name="EQUIPMENTID", type="VARCHAR", description="设备"),
                        ColumnSchema(name="SUMDATETIME", type="TIMESTAMP", description="发生时间"),
                    ],
                )
            ],
            relationships=[],
        )

    def test_generate_recommend_questions_parses_and_cleans_llm_json(self):
        from app.core.recommend_questions import generate_recommend_questions

        raw = json.dumps(
            {
                "questions": [
                    "最近 7 天报警次数趋势",
                    "各设备报警次数 Top10",
                    "最近 7 天报警次数趋势",
                    "",
                    "按报警码统计发生次数，并查看设备分布",
                ]
            },
            ensure_ascii=False,
        )

        with patch("app.core.recommend_questions.chat_completion", new=AsyncMock(return_value=raw)) as mocked:
            questions = asyncio.run(
                generate_recommend_questions(
                    datasource_name="alarm_detail",
                    source_type="excel",
                    metadata_prompt="报警明细包含 ALARMID、EQUIPMENTID、SUMDATETIME",
                    metrics_prompt="报警发生次数 = COUNT(*)",
                    schema=self._schema(),
                    limit=3,
                )
            )

        self.assertEqual(
            questions,
            [
                "最近 7 天报警次数趋势",
                "各设备报警次数 Top10",
                "按报警码统计发生次数，并查看设备分布",
            ],
        )
        prompt_payload = mocked.await_args.args[0][1]["content"]
        self.assertIn("alarm_detail", prompt_payload)
        self.assertIn("ALARMID", prompt_payload)

    def test_datasource_endpoint_returns_generated_questions_without_persisting(self):
        from app.api.datasource import generate_recommend_questions_for_datasource

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            current_user = User(id=1, username="admin", hashed_password="x", role="super_admin")
            datasource = DataSource(
                id=1,
                name="alarm_detail",
                slug="alarm-detail",
                database_url="sqlite:///:memory:",
                source_type="excel",
                metadata_prompt="报警明细包含 ALARMID、EQUIPMENTID、SUMDATETIME",
                schema_metadata=json.dumps(self._schema().model_dump(), ensure_ascii=False),
                recommend_questions=None,
            )
            db.add_all([current_user, datasource])
            db.commit()

            with patch(
                "app.api.datasource.generate_recommend_questions",
                new=AsyncMock(return_value=["最近 7 天报警次数趋势", "各设备报警次数 Top10"]),
            ):
                response = asyncio.run(
                    generate_recommend_questions_for_datasource(
                        datasource_id=datasource.id,
                        db=db,
                        current_user=current_user,
                    )
                )

            db.refresh(datasource)
            self.assertEqual(
                response,
                {"recommend_questions": ["最近 7 天报警次数趋势", "各设备报警次数 Top10"]},
            )
            self.assertIsNone(datasource.recommend_questions)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
