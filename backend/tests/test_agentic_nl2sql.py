import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx


class AgenticNl2SqlTests(unittest.TestCase):
    def test_agentic_nl2sql_does_not_clarify_ambiguous_request(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="sales(region, amount, created_at)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"needs_clarification":true,"reason":"缺少指标、时间范围和分组维度"}',
                    "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(build_agentic_nl2sql("看一下情况", datasource))

        self.assertEqual(mocked_chat.await_count, 2)
        self.assertEqual(result["sql_query"], "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region")
        self.assertNotIn("clarify", [item["stage"] for item in result["trace"]])

    def test_agentic_plan_clarification_payload_is_ignored(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Alarm DS",
            source_type="database",
            metadata_prompt="alarms(alarm_code, equipment_id, sumdatetime)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"needs_clarification":true,"reason":"缺少统计指标和时间范围",'
                    '"questions":["按报警次数还是按影响设备数统计？","需要看哪个时间范围？"]}',
                    "SELECT equipment_id, COUNT(*) AS alarm_count FROM alarms GROUP BY equipment_id",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(build_agentic_nl2sql("按设备看报警", datasource))

        self.assertEqual(mocked_chat.await_count, 2)
        self.assertEqual(
            result["sql_query"],
            "SELECT equipment_id, COUNT(*) AS alarm_count FROM alarms GROUP BY equipment_id",
        )
        self.assertEqual([item["stage"] for item in result["trace"]], ["context", "plan", "assumption", "sql_generate"])
        self.assertIn("agent_notes", result)
        self.assertIn("缺少统计指标和时间范围", result["agent_notes"]["assumptions"][0])
        self.assertGreaterEqual(len(result["agent_notes"]["suggested_refinements"]), 1)

    def test_agentic_nl2sql_rejects_non_read_only_sql(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="sales(region, amount)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"delete data","steps":["inspect"],"expected_output":"none"}',
                    "DELETE FROM sales",
                    "DELETE FROM sales",
                    "DELETE FROM sales",
                ]
            ),
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(build_agentic_nl2sql("删除所有销售数据", datasource))

        self.assertIn("只读", str(ctx.exception))

    def test_agentic_nl2sql_repairs_unsafe_sql_and_returns_trace(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="sales(region, amount)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"sum sales","steps":["choose table","aggregate"],"expected_output":"table"}',
                    "UPDATE sales SET amount = 0",
                    "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(build_agentic_nl2sql("按区域统计销售额", datasource, llm_model="pi/pi-mono"))

        self.assertEqual(
            result["sql_query"],
            "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
        )
        self.assertEqual(mocked_chat.await_count, 3)
        trace_by_stage = {item["stage"]: item for item in result["trace"]}
        self.assertEqual(trace_by_stage["context"]["detail"]["model"], "pi/pi-mono")
        self.assertEqual(trace_by_stage["plan"]["detail"]["plan"]["objective"], "sum sales")
        self.assertEqual(
            trace_by_stage["sql_fix"]["detail"]["sql"],
            "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
        )

    def test_agentic_context_filters_ignored_relationships_and_mentions_confidence_rule(self):
        from app.core.agentic_nl2sql import _build_datasource_context

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="",
            schema_metadata=json.dumps({
                "tables": [
                    {"name": "orders", "columns": [{"name": "customer_id", "type": "INTEGER"}]},
                    {"name": "customers", "columns": [{"name": "id", "type": "INTEGER"}]},
                    {"name": "wrong_table", "columns": [{"name": "id", "type": "INTEGER"}]},
                ],
                "relationships": [
                    {
                        "from_table": "orders",
                        "from_column": "customer_id",
                        "to_table": "customers",
                        "to_column": "id",
                        "status": "confirmed",
                        "confidence": 0.99,
                    },
                    {
                        "from_table": "orders",
                        "from_column": "customer_id",
                        "to_table": "ignored_target",
                        "to_column": "id",
                        "status": "ignored",
                        "confidence": 0.95,
                    },
                ],
            }),
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )

        context = _build_datasource_context(datasource)

        self.assertIn("只优先使用 confirmed", context)
        self.assertIn("customers", context)
        self.assertNotIn("ignored_target", context)

    def test_agentic_nl2sql_emits_trace_callback_in_order(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="sales(region, amount)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )
        emitted: list[dict] = []

        async def on_trace(item):
            emitted.append(item)

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"sum sales","steps":["aggregate"],"expected_output":"table"}',
                    "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
                ]
            ),
        ):
            result = asyncio.run(
                build_agentic_nl2sql("按区域统计销售额", datasource, on_trace=on_trace)
            )

        self.assertEqual(emitted, result["trace"])
        self.assertEqual([item["stage"] for item in emitted], ["context", "plan", "sql_generate"])

    def test_agentic_nl2sql_includes_value_probe_context_in_planning_prompt(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Alarm DS",
            source_type="excel",
            metadata_prompt="sheet1(STEP, ALARMID, SUMDATETIME)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="/tmp/alarm.xlsx",
        )
        probe_context = "值探测结果：SS 在 sheet1.STEP 中存在，匹配 12 条。"

        with patch(
            "app.core.agentic_nl2sql.detect_excel_join_risk",
            return_value=None,
        ), patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"trend","steps":["filter STEP"],"expected_output":"chart"}',
                    "SELECT STEP, ALARMID, COUNT(*) AS cnt FROM sheet1 WHERE STEP = 'SS' GROUP BY STEP, ALARMID",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(
                build_agentic_nl2sql(
                    "SS的step中，top10的alarm_id的次数趋势图",
                    datasource,
                    extra_context=probe_context,
                )
            )

        self.assertIn("WHERE STEP = 'SS'", result["sql_query"])
        planning_messages = mocked_chat.await_args_list[0].args[0]
        self.assertIn(probe_context, planning_messages[1]["content"])

    def test_agentic_nl2sql_uses_supplied_pi_config_for_llm_calls(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        datasource = SimpleNamespace(
            name="Sales DS",
            source_type="database",
            metadata_prompt="sales(region, amount)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="sqlite:///:memory:",
        )
        pi_config = {
            "provider": "pi",
            "base_url": "http://pi.example/v1",
            "api_key": "",
            "model": "pi/pi-mono",
            "temperature": 0,
            "agent_planner_mode": "llm_only",
        }

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"sum sales","steps":["aggregate"],"expected_output":"table"}',
                    "SELECT region, SUM(amount) AS total_amount FROM sales GROUP BY region",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(
                build_agentic_nl2sql("按区域统计销售额", datasource, llm_config=pi_config)
            )

        self.assertEqual(result["trace"][0]["detail"]["model"], "pi/pi-mono")
        self.assertEqual(mocked_chat.await_count, 2)
        for call in mocked_chat.await_args_list:
            self.assertEqual(call.kwargs["config_override"]["model"], "pi/pi-mono")

    def test_agentic_runtime_uses_system_llm_config_without_pi_override(self):
        from app.api.query import _resolve_agentic_llm_config

        config, model = _resolve_agentic_llm_config(
            {
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "api_key": "gemini-key",
                "model": "gemini-3.1-flash-lite",
                "temperature": 0.2,
                "agent_planner_mode": "llm_only",
            }
        )

        self.assertEqual(config["provider"], "gemini")
        self.assertEqual(config["model"], "gemini-3.1-flash-lite")
        self.assertEqual(model, "gemini-3.1-flash-lite")

    def test_agentic_chart_spec_recommends_facet_line_for_alarm_equipment_trend(self):
        from app.core.agentic_nl2sql import build_agentic_chart_spec

        result = {
            "columns": ["alarmcode", "equipmentid", "trend_date", "occurrence_count"],
            "rows": [
                {
                    "alarmcode": "2510",
                    "equipmentid": "EQ-1",
                    "trend_date": "2026-02-01",
                    "occurrence_count": 12,
                },
                {
                    "alarmcode": "2510",
                    "equipmentid": "EQ-2",
                    "trend_date": "2026-02-01",
                    "occurrence_count": 8,
                },
            ],
        }
        llm_config = {"model": "pi/pi-mono", "base_url": "http://pi.example/v1"}
        emitted: list[dict] = []

        async def on_trace(item):
            emitted.append(item)

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                return_value=(
                    '{"chart_type":"line","x_field":"trend_date","y_field":"occurrence_count",'
                    '"series_fields":["equipmentid"],"layout":"tabs_by_field",'
                    '"facet_field":"alarmcode","sort_order":"none","reason":"按 alarmcode 分页展示设备趋势"}'
                )
            ),
        ) as mocked_chat:
            planned = asyncio.run(
                build_agentic_chart_spec(
                    "TOP3的 alarmcode中发生次数最多的设备的趋势图 也取 TOP10",
                    result,
                    llm_model="pi/pi-mono",
                    llm_config=llm_config,
                    on_trace=on_trace,
                )
            )

        spec = planned["chart_spec"]
        self.assertEqual(spec["chart_type"], "line")
        self.assertEqual(spec["x_field"], "trend_date")
        self.assertEqual(spec["y_field"], "occurrence_count")
        self.assertEqual(spec["series_fields"], ["equipmentid"])
        self.assertEqual(spec["layout"], "tabs_by_field")
        self.assertEqual(spec["facet_field"], "alarmcode")
        self.assertEqual(emitted, planned["trace"])
        self.assertEqual(emitted[0]["stage"], "chart_plan")
        self.assertEqual(emitted[0]["detail"]["chart_spec"], spec)
        self.assertEqual(mocked_chat.await_args.kwargs["config_override"]["model"], "pi/pi-mono")

    def test_agentic_chart_spec_repairs_unfaceted_multi_dimension_trend(self):
        from app.core.agentic_nl2sql import build_agentic_chart_spec

        result = {
            "columns": ["ALARMID", "EQUIPMENTID", "trend_date", "count"],
            "rows": [
                {"ALARMID": 2059, "EQUIPMENTID": "EQ-1", "trend_date": "2026-02-01", "count": 10},
                {"ALARMID": 2510, "EQUIPMENTID": "EQ-1", "trend_date": "2026-02-01", "count": 20},
            ],
        }

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                return_value=(
                    '{"chart_type":"line","x_field":"trend_date","y_field":"count",'
                    '"series_fields":["EQUIPMENTID"],"layout":"single","sort_order":"none"}'
                )
            ),
        ):
            planned = asyncio.run(
                build_agentic_chart_spec(
                    "TOP3的 alarmcode中发生次数最多的设备的趋势图 也取 TOP10",
                    result,
                )
            )

        spec = planned["chart_spec"]
        self.assertEqual(spec["layout"], "tabs_by_field")
        self.assertEqual(spec["facet_field"], "ALARMID")
        self.assertEqual(spec["series_fields"], ["EQUIPMENTID"])

    def test_agentic_generation_error_mentions_system_llm_endpoint_when_connection_fails(self):
        from app.api.query import _format_agentic_generation_error

        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta")
        exc = httpx.ConnectError("All connection attempts failed", request=request)
        message = _format_agentic_generation_error(
            exc,
            {
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-3.1-flash-lite",
            },
        )

        self.assertIn("探索模式底层大模型连接失败", message)
        self.assertIn("gemini-3.1-flash-lite", message)
        self.assertIn("https://generativelanguage.googleapis.com/v1beta", message)

    def test_agentic_nl2sql_repairs_sql_after_execution_error(self):
        from app.core.agentic_nl2sql import repair_agentic_sql_after_execution_error

        datasource = SimpleNamespace(
            name="嘉盛半导体",
            source_type="database",
            metadata_prompt="detail(sumdatetime, equipmentid, error_code, count)",
            schema_metadata=None,
            metrics_prompt="",
            database_url="postgresql+psycopg2://user:pass@localhost:5432/jsemi",
        )
        failed_sql = (
            "SELECT sumdatetime FROM detail "
            "WHERE sumdatetime >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        )
        fixed_sql = "SELECT sumdatetime FROM detail WHERE sumdatetime >= NOW() - INTERVAL '30 days'"

        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(return_value=fixed_sql),
        ) as mocked_chat:
            result = asyncio.run(
                repair_agentic_sql_after_execution_error(
                    "最近30天异常趋势",
                    datasource,
                    {"objective": "trend", "steps": ["filter recent data"]},
                    failed_sql,
                    'syntax error at or near "30"',
                    llm_model="pi/pi-mono",
                )
            )

        self.assertEqual(result["sql_query"], fixed_sql)
        prompt = mocked_chat.await_args.args[0][1]["content"]
        self.assertIn("SQL 方言：PostgreSQL", prompt)
        self.assertIn("DATE_SUB(NOW(), INTERVAL 30 DAY)", prompt)
        self.assertIn('syntax error at or near "30"', prompt)
        trace_step = result["trace"][0]
        self.assertEqual(trace_step["stage"], "sql_execute_fix")
        self.assertEqual(trace_step["detail"]["model"], "pi/pi-mono")

    def test_agentic_execution_retries_after_database_error(self):
        from app.api.query import _execute_agentic_sql_with_repair

        datasource = SimpleNamespace(
            name="嘉盛半导体",
            source_type="database",
            database_url="postgresql+psycopg2://user:pass@localhost:5432/jsemi",
        )
        failed_sql = (
            "SELECT sumdatetime FROM detail "
            "WHERE sumdatetime >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        )
        fixed_sql = "SELECT sumdatetime FROM detail WHERE sumdatetime >= NOW() - INTERVAL '30 days'"
        executed_sql: list[str] = []

        def fake_execute(_datasource, sql):
            executed_sql.append(sql)
            if len(executed_sql) == 1:
                raise RuntimeError('syntax error at or near "30"')
            return {"columns": ["sumdatetime"], "rows": [{"sumdatetime": "2026-05-01"}]}, [
                {"sumdatetime": "2026-05-01"}
            ]

        async def fake_repair(*_args, **_kwargs):
            return {
                "sql_query": fixed_sql,
                "trace": [
                    {
                        "stage": "sql_execute_fix",
                        "status": "success",
                        "message": "已根据执行错误修复 SQL",
                        "detail": {"sql": fixed_sql},
                    }
                ],
            }

        agent_trace: list[dict] = []
        with (
            patch("app.api.query._execute_datasource_sql", side_effect=fake_execute),
            patch("app.api.query.repair_agentic_sql_after_execution_error", new=fake_repair),
        ):
            final_sql, result, rows = asyncio.run(
                _execute_agentic_sql_with_repair(
                    "最近30天异常趋势",
                    datasource,
                    failed_sql,
                    {"objective": "trend", "steps": ["filter recent data"]},
                    agent_trace,
                    llm_model="pi/pi-mono",
                )
            )

        self.assertEqual(executed_sql, [failed_sql, fixed_sql])
        self.assertEqual(final_sql, fixed_sql)
        self.assertEqual(rows, [{"sumdatetime": "2026-05-01"}])
        self.assertEqual(result["columns"], ["sumdatetime"])
        self.assertEqual(
            [item["stage"] for item in agent_trace],
            ["execute", "sql_execute_fix", "sql_execute_fix", "execute"],
        )
        self.assertEqual(agent_trace[0]["status"], "error")
        self.assertEqual(agent_trace[1]["status"], "pending")
        self.assertEqual(agent_trace[-1]["status"], "success")

    def test_agentic_execution_emits_repair_failure_trace_when_repair_call_fails(self):
        from app.api.query import _execute_agentic_sql_with_repair

        datasource = SimpleNamespace(
            name="嘉盛半导体",
            source_type="database",
            database_url="postgresql+psycopg2://user:pass@localhost:5432/jsemi",
        )

        def fake_execute(_datasource, _sql):
            raise RuntimeError('relation "detail" does not exist')

        async def fake_repair(*_args, **_kwargs):
            raise TimeoutError()

        emitted: list[dict] = []

        async def on_trace(item):
            emitted.append(item)

        agent_trace: list[dict] = []
        with (
            patch("app.api.query._execute_datasource_sql", side_effect=fake_execute),
            patch("app.api.query.repair_agentic_sql_after_execution_error", new=fake_repair),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(
                    _execute_agentic_sql_with_repair(
                        "TOP 设备趋势",
                        datasource,
                        "SELECT * FROM detail",
                        {"objective": "trend"},
                        agent_trace,
                        llm_model="pi/pi-mono",
                        on_trace=on_trace,
                    )
                )

        self.assertIn("SQL 修复失败: TimeoutError", str(ctx.exception))
        self.assertEqual(
            [item["stage"] for item in agent_trace],
            ["execute", "sql_execute_fix", "sql_execute_fix"],
        )
        self.assertEqual(agent_trace[1]["status"], "pending")
        self.assertEqual(agent_trace[2]["status"], "error")
        self.assertEqual(agent_trace[2]["detail"]["error_type"], "TimeoutError")
        self.assertEqual(emitted, agent_trace)

    def test_agentic_execution_error_detail_includes_trace_for_frontend(self):
        from app.api.query import _build_query_execution_error_detail

        trace = [
            {"stage": "execute", "status": "error", "message": "SQL 执行失败"},
            {"stage": "sql_execute_fix", "status": "success", "message": "已修复 SQL"},
        ]

        detail = _build_query_execution_error_detail(
            "agentic",
            "SQL执行失败: relation detail does not exist",
            "SELECT * FROM detail",
            trace,
            "pi/pi-mono",
        )

        self.assertEqual(detail["message"], "SQL执行失败: relation detail does not exist")
        self.assertEqual(detail["sql_query"], "SELECT * FROM detail")
        self.assertEqual(detail["agent_trace"], trace)
        self.assertEqual(detail["llm_model"], "pi/pi-mono")

    def test_sse_event_serializes_named_event(self):
        from app.api.query import _sse_event

        payload = {"stage": "context", "message": "已读取数据源元数据"}

        encoded = _sse_event("trace", payload)

        self.assertTrue(encoded.startswith("event: trace\n"))
        self.assertIn('"stage": "context"', encoded)
        self.assertIn('"message": "已读取数据源元数据"', encoded)
        self.assertTrue(encoded.endswith("\n\n"))

    def test_stream_unhandled_error_detail_preserves_partial_trace(self):
        from app.api.query import _build_agentic_stream_unhandled_error_detail

        trace = [{"stage": "execute", "status": "success", "message": "已执行查询"}]

        detail = _build_agentic_stream_unhandled_error_detail(
            RuntimeError("history insert failed"),
            "SELECT * FROM alarms",
            trace,
            "pi/pi-mono",
        )

        self.assertIn("流式问数失败", detail["message"])
        self.assertEqual(detail["sql_query"], "SELECT * FROM alarms")
        self.assertEqual(detail["llm_model"], "pi/pi-mono")
        self.assertEqual(detail["agent_trace"][0], trace[0])
        self.assertEqual(detail["agent_trace"][-1]["stage"], "stream_finalize")
        self.assertEqual(detail["agent_trace"][-1]["status"], "error")

    def test_non_agentic_execution_error_detail_stays_string(self):
        from app.api.query import _build_query_execution_error_detail

        detail = _build_query_execution_error_detail(
            "business",
            "SQL执行失败: relation detail does not exist",
            "SELECT * FROM detail",
            [{"stage": "execute", "status": "error", "message": "SQL 执行失败"}],
            "pi/pi-mono",
        )

        self.assertEqual(detail, "SQL执行失败: relation detail does not exist")


if __name__ == "__main__":
    unittest.main()
