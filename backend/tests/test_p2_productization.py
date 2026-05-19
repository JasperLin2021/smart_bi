import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class P2ProductizationTests(unittest.TestCase):
    def _db(self, tables):
        from app.db.base_class import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=tables)
        return sessionmaker(bind=engine)()

    def test_organization_model_does_not_expose_commercial_package_fields(self):
        from app.models.organization import Organization

        for field in (
            "plan_type",
            "user_limit",
            "datasource_limit",
            "dashboard_limit",
            "big_screen_limit",
            "monthly_query_limit",
            "white_label_enabled",
            "branding_json",
        ):
            self.assertFalse(hasattr(Organization, field), field)

    def test_datasource_creation_stays_unlimited_for_each_org(self):
        from app.api.datasource import create_datasource
        from app.models.audit_log import AuditLog
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.schemas.datasource import DataSourceCreate

        db = self._db([Organization.__table__, DataSource.__table__, AuditLog.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        db.add_all(
            [
                DataSource(
                    name=f"Existing {index}",
                    slug=f"existing-{index}",
                    database_url="sqlite:///:memory:",
                    metadata_prompt="",
                    org_id=org.id,
                )
                for index in range(10)
            ]
        )
        db.commit()

        created = create_datasource(
            DataSourceCreate(
                name="Next",
                slug="next",
                database_url="sqlite:///:memory:",
                metadata_prompt="",
                org_id=org.id,
            ),
            db=db,
            current_user=SimpleNamespace(id=1, username="root", role="super_admin", org_id=None),
        )

        self.assertEqual(created["name"], "Next")
        self.assertEqual(db.query(DataSource).filter(DataSource.org_id == org.id).count(), 11)

    def test_data_service_catalog_lists_metric_and_dashboard_contracts(self):
        from app.api.data_services import get_data_service_catalog
        from app.models.dashboard_config import Dashboard
        from app.models.datasource import DataSource
        from app.models.metric import Metric
        from app.models.organization import Organization

        db = self._db([Organization.__table__, DataSource.__table__, Metric.__table__, Dashboard.__table__])
        org = Organization(name="Acme", slug="acme")
        db.add(org)
        db.flush()
        ds = DataSource(name="Sales", slug="sales", database_url="sqlite:///:memory:", metadata_prompt="", org_id=org.id)
        db.add(ds)
        db.flush()
        metric = Metric(
            datasource_id=ds.id,
            name="GMV",
            definition="成交额",
            formula="SUM(amount)",
            status="published",
            certification_status="certified",
        )
        dashboard = Dashboard(title="经营看板", status="published", visibility="org", org_id=org.id, owner_id=2)
        db.add_all([metric, dashboard])
        db.commit()

        catalog = get_data_service_catalog(
            db=db,
            current_user=SimpleNamespace(id=2, username="admin", role="org_admin", org_id=org.id),
        )

        self.assertEqual(catalog["metrics"][0]["name"], "GMV")
        self.assertEqual(catalog["metrics"][0]["api_contract"]["endpoint"], f"/api/data-services/metrics/{metric.id}")
        self.assertEqual(catalog["dashboards"][0]["title"], "经营看板")
        self.assertIn("embed", catalog["sdk_examples"]["dashboard_embed"])

    def test_auto_insights_and_attribution_surface_business_drivers(self):
        from app.api.insights import (
            AnomalyAttributionRequest,
            AutoInsightsRequest,
            auto_insights,
            anomaly_attribution,
        )

        rows = [
            {"region": "华东", "month": "2026-01", "revenue": 120},
            {"region": "华南", "month": "2026-01", "revenue": 80},
            {"region": "华北", "month": "2026-01", "revenue": -30},
        ]

        insights = asyncio.run(
            auto_insights(
                AutoInsightsRequest(columns=["region", "month", "revenue"], rows=rows),
                current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
            )
        )
        attribution = asyncio.run(
            anomaly_attribution(
                AnomalyAttributionRequest(
                    columns=["region", "month", "revenue"],
                    rows=rows,
                    metric_column="revenue",
                    dimension_columns=["region"],
                ),
                current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
            )
        )

        self.assertGreaterEqual(len(insights["insights"]), 2)
        self.assertEqual(attribution["metric_column"], "revenue")
        self.assertEqual(attribution["drivers"][0]["dimension"], "region")
        self.assertEqual(attribution["drivers"][0]["value"], "华东")

    def test_auto_insights_uses_system_llm_to_enrich_rule_evidence(self):
        from app.api.insights import AutoInsightsRequest, auto_insights

        rows = [
            {"region": "华东", "revenue": 120},
            {"region": "华南", "revenue": 80},
        ]

        async def fake_config():
            return {
                "provider": "deepseek",
                "base_url": "http://llm.example/v1",
                "api_key": "",
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
            }

        with patch("app.api.insights.get_llm_config", new=fake_config), patch(
            "app.api.insights.chat_completion",
            new=AsyncMock(
                return_value=json.dumps(
                    {
                        "summary": "LLM 基于规则证据识别华东为主要贡献区域。",
                        "insights": [
                            {
                                "type": "top_driver",
                                "title": "华东贡献最突出",
                                "description": "规则统计显示华东 revenue 为 120，应优先解释其来源。",
                                "severity": "success",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            ),
        ) as mocked_chat:
            result = asyncio.run(
                auto_insights(
                    AutoInsightsRequest(columns=["region", "revenue"], rows=rows),
                    current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
                )
            )

        self.assertEqual(result["summary"], "LLM 基于规则证据识别华东为主要贡献区域。")
        self.assertEqual(result["insights"][0]["title"], "华东贡献最突出")
        self.assertTrue(result["metadata"]["llm_enhanced"])
        self.assertEqual(result["metadata"]["llm_model"], "deepseek-v4-flash")
        self.assertEqual(mocked_chat.await_args.kwargs["config_override"]["model"], "deepseek-v4-flash")

    def test_anomaly_attribution_uses_llm_for_explanation_but_keeps_numeric_drivers(self):
        from app.api.insights import AnomalyAttributionRequest, anomaly_attribution

        rows = [
            {"region": "华东", "revenue": 120},
            {"region": "华北", "revenue": -30},
        ]

        async def fake_config():
            return {
                "provider": "deepseek",
                "base_url": "http://llm.example/v1",
                "api_key": "",
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
            }

        with patch("app.api.insights.get_llm_config", new=fake_config), patch(
            "app.api.insights.chat_completion",
            new=AsyncMock(
                return_value=json.dumps(
                    {
                        "summary": "LLM 建议优先核查华东贡献来源，并关注华北负向项。",
                        "recommendations": ["核对华东明细来源", "为华北负值创建行动项"],
                    },
                    ensure_ascii=False,
                )
            ),
        ):
            result = asyncio.run(
                anomaly_attribution(
                    AnomalyAttributionRequest(
                        columns=["region", "revenue"],
                        rows=rows,
                        metric_column="revenue",
                        dimension_columns=["region"],
                    ),
                    current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
                )
            )

        self.assertEqual(result["summary"], "LLM 建议优先核查华东贡献来源，并关注华北负向项。")
        self.assertEqual(result["recommendations"], ["核对华东明细来源", "为华北负值创建行动项"])
        self.assertEqual(result["drivers"][0]["contribution"], 120)
        self.assertTrue(result["llm_enhanced"])

    def test_anomaly_precheck_detects_candidate_and_uses_system_llm(self):
        from app.api.insights import AnomalyPrecheckRequest, anomaly_precheck

        rows = [
            {"day": "2026-05-01", "alarm_count": 10},
            {"day": "2026-05-02", "alarm_count": 12},
            {"day": "2026-05-03", "alarm_count": 11},
            {"day": "2026-05-04", "alarm_count": 80},
        ]

        async def fake_config():
            return {
                "provider": "deepseek",
                "base_url": "http://llm.example/v1",
                "api_key": "",
                "model": "deepseek-v4-flash",
                "temperature": 0.2,
            }

        with patch("app.api.insights.get_llm_config", new=fake_config), patch(
            "app.api.insights.chat_completion",
            new=AsyncMock(
                return_value=json.dumps(
                    {
                        "summary": "检测到 2026-05-04 alarm_count 明显高于前序水平，建议做异常归因。",
                        "anomalies": [
                            {
                                "type": "trend_spike",
                                "title": "alarm_count 突增",
                                "description": "2026-05-04 的 alarm_count 为 80，明显高于前序值。",
                                "severity": "warning",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            ),
        ) as mocked_chat:
            result = asyncio.run(
                anomaly_precheck(
                    AnomalyPrecheckRequest(
                        columns=["day", "alarm_count"],
                        rows=rows,
                        question="报警数是否异常",
                    ),
                    current_user=SimpleNamespace(id=1, username="analyst", role="user", org_id=1),
                )
            )

        self.assertEqual(result["status"], "anomaly")
        self.assertTrue(result["has_anomaly"])
        self.assertEqual(result["recommended_action"], "anomaly_attribution")
        self.assertEqual(result["action_label"], "查看异常归因")
        self.assertTrue(result["llm_enhanced"])
        self.assertEqual(result["llm_model"], "deepseek-v4-flash")
        self.assertEqual(mocked_chat.await_args.kwargs["config_override"]["model"], "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
