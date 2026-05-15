import unittest


class MetricPromptSyncTests(unittest.TestCase):
    def _db(self, tables):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_build_metrics_prompt_lists_active_metrics(self):
        from app.core.metric_prompt_sync import build_metrics_prompt

        prompt = build_metrics_prompt(
            [
                {
                    "name": "OEE",
                    "description": "设备综合效率",
                    "definition": "OEE = 时间开动率 × 性能效率 × 良品率",
                    "formula": "AVG(mainrecord.OEE)",
                    "calculation_config": {
                        "statistical_window": "自然日",
                        "time_grain": "day",
                        "filters": [
                            {"field": "factory", "operator": "=", "value": "A厂"}
                        ],
                        "null_handling": "停机时间为空按 0 处理",
                        "dedup_key": "machine_id + shift_date",
                    },
                },
                {
                    "name": "产出",
                    "description": "",
                    "definition": "在实际生产中，最终做出来了多少",
                    "formula": "SUM(production.OKCOUNT)",
                },
            ]
        )

        self.assertIn("可用指标：", prompt)
        self.assertIn("OEE", prompt)
        self.assertIn("AVG(mainrecord.OEE)", prompt)
        self.assertIn("统计周期：自然日", prompt)
        self.assertIn("时间粒度：day", prompt)
        self.assertIn("过滤条件：factory = A厂", prompt)
        self.assertIn("空值处理：停机时间为空按 0 处理", prompt)
        self.assertIn("去重键：machine_id + shift_date", prompt)
        self.assertIn("产出", prompt)

    def test_build_metrics_prompt_returns_none_for_empty_metrics(self):
        from app.core.metric_prompt_sync import build_metrics_prompt

        self.assertIsNone(build_metrics_prompt([]))

    def test_sync_datasource_metrics_prompt_excludes_untrusted_metrics(self):
        from app.core.metric_prompt_sync import sync_datasource_metrics_prompt
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization

        db = self._db([Organization.__table__, DataSource.__table__, Metric.__table__])
        datasource = DataSource(
            name="Nexteer",
            slug="nexteer",
            database_url="sqlite:///:memory:",
            source_type="excel",
            metadata_prompt="",
            org_id=1,
        )
        db.add(datasource)
        db.flush()
        db.add_all(
            [
                Metric(
                    datasource_id=datasource.id,
                    dataset_id=1,
                    name="产出",
                    definition="TOTALCOUNT 合计",
                    formula="SUM(mainrecord.TOTALCOUNT)",
                    status="published",
                    certification_status="certified",
                    is_active=1,
                ),
                Metric(
                    datasource_id=datasource.id,
                    dataset_id=1,
                    name="线产出",
                    definition="已下架：与产出口径重复",
                    formula="SUM(mainrecord.TOTALCOUNT)",
                    status="archived",
                    certification_status="deprecated",
                    is_active=1,
                ),
                Metric(
                    datasource_id=datasource.id,
                    dataset_id=1,
                    name="旧产出",
                    definition="废弃指标",
                    formula="SUM(mainrecord.TOTALCOUNT)",
                    status="published",
                    certification_status="deprecated",
                    is_active=1,
                ),
                Metric(
                    datasource_id=datasource.id,
                    dataset_id=1,
                    name="停用产出",
                    definition="停用指标",
                    formula="SUM(mainrecord.TOTALCOUNT)",
                    status="published",
                    certification_status="certified",
                    is_active=0,
                ),
            ]
        )
        db.commit()

        sync_datasource_metrics_prompt(db, datasource.id)

        self.assertIn("- 产出:", datasource.metrics_prompt)
        self.assertNotIn("线产出", datasource.metrics_prompt)
        self.assertNotIn("旧产出", datasource.metrics_prompt)
        self.assertNotIn("停用产出", datasource.metrics_prompt)


if __name__ == "__main__":
    unittest.main()
