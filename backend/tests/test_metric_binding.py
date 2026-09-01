import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class MetricBindingTests(unittest.TestCase):
    def test_match_metric_from_question_prefers_exact_name(self):
        from app.core.metric_binding import match_metric_from_question

        datasource = SimpleNamespace(
            metrics_prompt="可用指标：\n- 总产出: 计算公式：SUM(output_qty)\n- 良率: 计算公式：SUM(good_qty) / SUM(output_qty)"
        )

        matched = match_metric_from_question("请看今天的良率趋势", datasource)

        self.assertIsNotNone(matched)
        self.assertEqual(matched["name"], "良率")
        self.assertEqual(matched["formula"], "SUM(good_qty) / SUM(output_qty)")

    def test_generate_safe_sql_retries_when_target_metric_formula_missing(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "良率",
            "formula": "SUM(good_qty) / SUM(output_qty)",
        }
        first_sql = "SELECT COUNT(*) AS 良率 FROM prod"
        second_sql = "SELECT SUM(good_qty) / SUM(output_qty) AS 良率 FROM prod"

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": first_sql}, {"sql": second_sql}]),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("查询良率", datasource, metric_match=metric_match))

        self.assertEqual(sql, second_sql)
        self.assertEqual(mocked_generate.await_count, 2)
        _, second_kwargs = mocked_generate.await_args_list[1]
        self.assertIn("没有使用目标指标", second_kwargs["context"])

    def test_generate_safe_sql_retries_when_metric_fixed_filter_missing(self):
        """指标公式自带固定筛选时，SQL 漏掉筛选（如漏 order_status='delivered'）应触发重写。"""
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "月订单数量",
            "formula": "COUNT(orders.order_id) WHERE orders.order_status = 'delivered'",
        }
        first_sql = "SELECT COUNT(orders.order_id) AS c FROM orders"
        second_sql = "SELECT COUNT(orders.order_id) AS c FROM orders WHERE order_status = 'delivered'"

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": first_sql}, {"sql": second_sql}]),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("查询月订单数量", datasource, metric_match=metric_match))

        self.assertEqual(sql, second_sql)
        self.assertEqual(mocked_generate.await_count, 2)
        _, second_kwargs = mocked_generate.await_args_list[1]
        self.assertIn("没有使用目标指标公式", second_kwargs["context"])
        self.assertIn("order_status = 'delivered'", second_kwargs["context"])

    def test_generate_safe_sql_raises_when_metric_formula_still_missing(self):
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "良率",
            "formula": "SUM(good_qty) / SUM(output_qty)",
        }

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": "SELECT COUNT(*) FROM prod"}, {"sql": "SELECT AVG(score) FROM prod"}]),
        ), patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(_generate_safe_sql("查询良率", datasource, metric_match=metric_match))

        self.assertIn("目标指标公式", str(ctx.exception))

    def test_generate_safe_sql_retries_when_metric_time_field_mismatch(self):
        """指标配置了时间字段时，SQL 用错时间字段（如下单时间 vs 审批时间）应触发重写。"""
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "DAU",
            "formula": "COUNT(DISTINCT orders.customer_id)",
            "time_field": "orders.order_approved_at",
        }
        first_sql = (
            "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
            "WHERE order_purchase_timestamp >= '2016-10-10' AND order_purchase_timestamp < '2016-10-11'"
        )
        second_sql = (
            "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
            "WHERE order_approved_at >= '2016-10-10' AND order_approved_at < '2016-10-11'"
        )

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": first_sql}, {"sql": second_sql}]),
        ) as mocked_generate, patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            sql = asyncio.run(_generate_safe_sql("2016年10月10日的dau是多少", datasource, metric_match=metric_match))

        self.assertEqual(sql, second_sql)
        self.assertEqual(mocked_generate.await_count, 2)
        _, second_kwargs = mocked_generate.await_args_list[1]
        self.assertIn("order_approved_at", second_kwargs["context"])

    def test_generate_safe_sql_raises_when_metric_time_field_still_missing(self):
        """时间字段重试后仍用错字段，应直接报错而不是返回口径错误的结果。"""
        from app.api.query import _generate_safe_sql

        datasource = SimpleNamespace(
            source_type="postgres",
            database_url="postgresql://example",
        )
        metric_match = {
            "name": "DAU",
            "formula": "COUNT(DISTINCT orders.customer_id)",
            "time_field": "orders.order_approved_at",
        }
        bad_sql = (
            "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
            "WHERE order_purchase_timestamp >= '2016-10-10'"
        )

        with patch(
            "app.api.query.generate_sql_query",
            new=AsyncMock(side_effect=[{"sql": bad_sql}, {"sql": bad_sql}]),
        ), patch(
            "app.api.query.detect_excel_join_risk",
            return_value=None,
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(_generate_safe_sql("2016年10月10日的dau是多少", datasource, metric_match=metric_match))

        self.assertIn("目标指标公式", str(ctx.exception))

    def test_metric_time_field_extracted_from_calculation_config(self):
        from app.core.metric_binding import _metric_time_field

        self.assertEqual(
            _metric_time_field(SimpleNamespace(calculation_config={"time_field": "orders.order_approved_at"})),
            "orders.order_approved_at",
        )
        self.assertEqual(_metric_time_field(SimpleNamespace(calculation_config={})), "")
        self.assertEqual(
            _metric_time_field(
                SimpleNamespace(calculation_config={"statistical_scope": {"time_field": "orders.order_approved_at"}})
            ),
            "orders.order_approved_at",
        )
        self.assertEqual(
            _metric_time_field(SimpleNamespace(calculation_config='{"time_field": "orders.order_approved_at"}')),
            "orders.order_approved_at",
        )

    def test_resolve_time_field_derived_column_maps_to_source_column(self):
        from app.core.metric_binding import _resolve_time_field

        dataset = SimpleNamespace(
            id=110,
            fields_json={
                "fields": [
                    "orders.order_status",
                    "orders.order_approved_at",
                    "customers.customer_id",
                ]
            },
            derived_columns_json={
                "expressions": [
                    "Datetime_YMD = TO_CHAR(order_approved_at, 'YYYY\"年\"MM\"月\"DD\"日\"')",
                    "Delivery_Completion_Rate = ROUND(SUM(Delivery_completion)/COUNT(order_id),2)",
                ]
            },
        )
        db = SimpleNamespace(
            query=lambda model: SimpleNamespace(
                filter=lambda *a, **k: SimpleNamespace(first=lambda: dataset)
            )
        )
        metric = SimpleNamespace(dataset_id=110, calculation_config={"time_field": "Datetime_YMD"})
        self.assertEqual(_resolve_time_field(db, metric), "orders.order_approved_at")

        # 派生列表达式无法解析出列 -> 回退原值
        bad_dataset = SimpleNamespace(
            id=110,
            fields_json={},
            derived_columns_json={"expressions": ["Custom = 1 + 2"]},
        )
        bad_db = SimpleNamespace(
            query=lambda model: SimpleNamespace(
                filter=lambda *a, **k: SimpleNamespace(first=lambda: bad_dataset)
            )
        )
        self.assertEqual(_resolve_time_field(bad_db, metric), "Datetime_YMD")

        # 结构二：{"name": "expr"} 直接映射
        dict_dataset = SimpleNamespace(
            id=110,
            fields_json={},
            derived_columns_json={"Datetime": "TO_CHAR(order_approved_at, 'YYYY\"年\"MM\"月\"')"},
        )
        dict_db = SimpleNamespace(
            query=lambda model: SimpleNamespace(
                filter=lambda *a, **k: SimpleNamespace(first=lambda: dict_dataset)
            )
        )
        metric5 = SimpleNamespace(dataset_id=110, calculation_config={"time_field": "Datetime"})
        self.assertEqual(_resolve_time_field(dict_db, metric5), "order_approved_at")

        # 非派生列 -> 原样返回
        metric2 = SimpleNamespace(
            dataset_id=110,
            calculation_config={"time_field": "orders.order_approved_at"},
        )
        self.assertEqual(_resolve_time_field(db, metric2), "orders.order_approved_at")

        # 未配置时间字段 -> 空
        metric3 = SimpleNamespace(dataset_id=110, calculation_config={})
        self.assertEqual(_resolve_time_field(db, metric3), "")

        # 数据集不存在 -> 原样返回
        empty_db = SimpleNamespace(
            query=lambda model: SimpleNamespace(
                filter=lambda *a, **k: SimpleNamespace(first=lambda: None)
            )
        )
        metric4 = SimpleNamespace(
            dataset_id=999,
            calculation_config={"time_field": "Datetime_YMD"},
        )
        self.assertEqual(_resolve_time_field(empty_db, metric4), "Datetime_YMD")

    def test_sql_uses_metric_time_field_checks_where_column(self):
        from app.core.metric_binding import sql_uses_metric_time_field

        # 使用正确时间字段 -> 通过
        self.assertTrue(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
                "WHERE order_approved_at >= '2016-10-10' AND order_approved_at < '2016-10-11'",
                "orders.order_approved_at",
            )
        )
        # 时间字段被函数包裹（DATE/CAST）或带别名 -> 仍通过
        self.assertTrue(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders WHERE DATE(order_approved_at) = '2016-10-10'",
                "orders.order_approved_at",
            )
        )
        self.assertTrue(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders WHERE o.order_approved_at::date = '2016-10-10'",
                "orders.order_approved_at",
            )
        )
        # 用错时间字段 -> 拦截
        self.assertFalse(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
                "WHERE order_purchase_timestamp >= '2016-10-10' AND order_purchase_timestamp < '2016-10-11'",
                "orders.order_approved_at",
            )
        )
        # 无 WHERE / 未配置时间字段 -> 不做约束
        self.assertTrue(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders",
                "orders.order_approved_at",
            )
        )
        self.assertTrue(
            sql_uses_metric_time_field(
                "SELECT COUNT(DISTINCT customer_id) AS dau FROM orders "
                "WHERE order_purchase_timestamp >= '2016-10-10'",
                "",
            )
        )

    def test_sql_uses_metric_formula_accepts_equivalent_join_filter_sql(self):
        from app.core.metric_binding import sql_uses_metric_formula

        formula = (
            "SUM(production.OKCOUNT) "
            "WHERE production.MAINID IN "
            "(SELECT ID FROM mainrecord WHERE LINE = 'REPS3 Final')"
        )
        sql = (
            "SELECT SUM(p.OKCOUNT) AS 线产出 "
            "FROM production p "
            "JOIN mainrecord m ON p.MAINID = m.ID "
            "WHERE m.LINE = 'REPS3 Final'"
        )

        self.assertTrue(sql_uses_metric_formula(sql, formula))


class MetricAstValidationTests(unittest.TestCase):
    """AST 结构级口径校验：拦截"公式+额外变换"，放行等价写法。"""

    def test_rejects_metric_formula_with_extra_transformation(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT SUM(amount) + 100 AS total FROM orders",
                "SUM(amount)",
            )
        )

    def test_rejects_multiplied_metric_formula(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT SUM(amount * 2) AS total FROM orders",
                "SUM(amount)",
            )
        )

    def test_accepts_round_wrapped_metric_formula(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT ROUND(SUM(amount), 2) AS total FROM orders",
                "SUM(amount)",
            )
        )

    def test_accepts_nullif_and_coalesce_zero_safe_wrappers(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT SUM(good_qty) / NULLIF(SUM(output_qty), 0) AS rate FROM prod",
                "SUM(good_qty) / SUM(output_qty)",
            )
        )
        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT SUM(good_qty) / COALESCE(SUM(output_qty), 0) AS rate FROM prod",
                "SUM(good_qty) / SUM(output_qty)",
            )
        )

    def test_accepts_numeric_cast_in_ratio_formula(self):
        """交付完成率场景：LLM 为避免整数除法加的 ::numeric 属数值类型提升，应视为口径等价。"""
        from app.core.metric_binding import sql_uses_metric_formula

        formula = "ROUND(SUM(delivery_completion)/COUNT(order_id), 2)"
        sql = (
            "SELECT DATE(order_purchase_timestamp) AS stat_date, "
            "ROUND(SUM(delivery_completion)::numeric / COUNT(order_id), 2) AS delivery_completion_rate "
            "FROM orders "
            "WHERE order_purchase_timestamp >= '2016-10-09' AND order_purchase_timestamp < '2016-10-10' "
            "GROUP BY DATE(order_purchase_timestamp)"
        )
        self.assertTrue(sql_uses_metric_formula(sql, formula))

    def test_accepts_common_numeric_cast_variants(self):
        """float / double precision / decimal(精度) / int 等数值类型提升 CAST 均不应误判为口径偏离。"""
        from app.core.metric_binding import sql_uses_metric_formula

        formula = "SUM(amount) / SUM(qty)"
        for cast in ("::float", "::double precision", "::decimal(10,2)", "::numeric", "::int"):
            self.assertTrue(
                sql_uses_metric_formula(
                    f"SELECT SUM(amount){cast} / SUM(qty) AS avg_price FROM sales",
                    formula,
                ),
                f"cast {cast} 应被放行",
            )

    def test_still_rejects_semantic_cast_tampering(self):
        """::text / ::date 等语义转换不属于数值类型提升，加在公式上仍应判为口径偏离。"""
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT SUM(amount)::text AS total FROM orders",
                "SUM(amount)",
            )
        )
        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT SUM(amount)::date AS total FROM orders",
                "SUM(amount)",
            )
        )

    def test_rejects_where_filter_tampering(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT SUM(amount) AS total FROM orders WHERE status = 'invalid'",
                "SUM(amount) WHERE status = 'valid'",
            )
        )

    def test_accepts_matching_where_filter(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT SUM(amount) AS total FROM orders WHERE status = 'valid'",
                "SUM(amount) WHERE status = 'valid'",
            )
        )

    def test_accepts_alias_and_qualified_columns(self):
        from app.core.metric_binding import sql_uses_metric_formula

        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT SUM(p.OKCOUNT) AS 线产出 FROM production p GROUP BY p.LINE",
                "SUM(production.OKCOUNT)",
            )
        )

    def test_rejects_sql_missing_metric_fixed_filter(self):
        """指标公式自带固定筛选时，SQL 漏掉筛选（如漏 order_status='delivered'）应判为不通过。"""
        from app.core.metric_binding import sql_uses_metric_formula

        formula = "COUNT(orders.order_id) WHERE orders.order_status = 'delivered'"
        self.assertFalse(
            sql_uses_metric_formula(
                "SELECT COUNT(orders.order_id) AS c FROM orders "
                "WHERE TO_CHAR(order_approved_at, 'YYYY-MM') = '2018-08'",
                formula,
            )
        )

    def test_accepts_sql_with_metric_fixed_filter(self):
        """SQL 包含指标固定筛选（含表限定/别名等价写法）时应通过。"""
        from app.core.metric_binding import sql_uses_metric_formula

        formula = "COUNT(orders.order_id) WHERE orders.order_status = 'delivered'"
        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT COUNT(orders.order_id) AS c FROM orders "
                "WHERE order_status = 'delivered' AND TO_CHAR(order_approved_at, 'YYYY-MM') = '2018-08'",
                formula,
            )
        )
        self.assertTrue(
            sql_uses_metric_formula(
                "SELECT COUNT(o.order_id) AS c FROM orders o WHERE o.order_status = 'delivered'",
                formula,
            )
        )


class MetricTableMatchingTests(unittest.TestCase):
    """match_metrics_from_question：直接读 Metric 表、certified 优先、多候选。"""

    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.base_class import Base
        from app.models.organization import Organization  # noqa: F401
        from app.models.metric import Metric

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine, tables=[Metric.__table__])
        Session = sessionmaker(bind=engine)
        return Session(), engine

    def _metric(
        self,
        name,
        formula,
        certification_status="draft",
        is_active=1,
        status="published",
        dataset_id=None,
        calculation_config=None,
    ):
        from app.models.metric import Metric

        return Metric(
            datasource_id=1,
            name=name,
            definition=name,
            formula=formula,
            unit="%",
            aggregation="sum",
            status=status,
            certification_status=certification_status,
            caliber_version="v1",
            quality_status="normal",
            is_active=is_active,
            dataset_id=dataset_id,
            calculation_config=calculation_config,
        )

    def test_returns_empty_when_no_match(self):
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add(self._metric("回款率", "SUM(received_amount) / SUM(receivable_amount)"))
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "今天天气怎么样", datasource)
            self.assertEqual(matched, [])
        finally:
            engine.dispose()

    def test_certified_metric_ranked_first_when_same_score(self):
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add_all(
                [
                    self._metric("毛利率", "SUM(profit) / SUM(revenue)", certification_status="draft"),
                    self._metric("毛利", "SUM(profit)", certification_status="certified"),
                ]
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "查询毛利率", datasource)
            self.assertEqual(len(matched), 2)
            self.assertEqual(matched[0]["name"], "毛利")  # certified 优先
            self.assertEqual(matched[0]["certification_status"], "certified")
            self.assertEqual(matched[1]["name"], "毛利率")
        finally:
            engine.dispose()

    def test_matches_bracketed_alias(self):
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add(self._metric("订单金额(含税)", "SUM(amount + tax)", certification_status="certified"))
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "统计含税金额", datasource)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["name"], "订单金额(含税)")
        finally:
            engine.dispose()

    def test_excludes_deprecated_and_inactive_metrics(self):
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add_all(
                [
                    self._metric("销售额", "SUM(amount)", certification_status="deprecated"),
                    self._metric("订单量", "COUNT(id)", is_active=0),
                ]
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "查询销售额和订单量", datasource)
            self.assertEqual(matched, [])
        finally:
            engine.dispose()

    def test_excludes_unpublished_draft_status_metrics(self):
        """未发布（status=draft）的指标不会被问数命中——这是"指标未注入口径"的常见根因。"""
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add(
                self._metric(
                    "交付完成率",
                    "ROUND(SUM(delivery_completion)/COUNT(order_id), 2)",
                    status="draft",
                    certification_status="certified",
                )
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "2016-10-9的交付完成率是多少", datasource)
            self.assertEqual(matched, [])
        finally:
            engine.dispose()

    def test_returns_all_candidates_sorted_by_score(self):
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add_all(
                [
                    self._metric("销售额", "SUM(amount)"),
                    self._metric("销售额(含税)", "SUM(amount + tax)"),
                ]
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "查询销售额含税", datasource)
            # "销售额" 原名命中（子串）优先于 "销售额(含税)" 的分词命中
            self.assertEqual(matched[0]["name"], "销售额")
            self.assertEqual(len(matched), 2)
        finally:
            engine.dispose()

    def test_explicit_reference_wins_across_datasets(self):
        """问题显式引用指标名时，指标口径优先于当前数据集作用域（用户指定「月订单数量」场景）。"""
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add_all(
                [
                    self._metric("每日GMV", "SUM(payment_value)", certification_status="draft", dataset_id=107),
                    self._metric(
                        "月订单数量", "COUNT(orders.order_id)", certification_status="certified", dataset_id=110
                    ),
                ]
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(
                db, "2018年8月的订单数量是多少，请参考月订单数量指标", datasource, dataset_id=107
            )
            self.assertEqual(matched[0]["name"], "月订单数量")
            self.assertEqual(matched[0]["formula"], "COUNT(orders.order_id)")
        finally:
            engine.dispose()

    def test_partial_substring_hit_without_explicit_reference(self):
        """无显式引用时，「订单数量」仍可通过中文连续子串命中「月订单数量」，并跨越数据集降权保留候选。"""
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add_all(
                [
                    self._metric(
                        "月订单数量", "COUNT(orders.order_id)", certification_status="certified", dataset_id=110
                    ),
                    self._metric("查看订单均价", "AVG(payment_value)", certification_status="certified", dataset_id=107),
                ]
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(db, "2018年8月的订单数量是多少", datasource, dataset_id=107)
            self.assertGreaterEqual(len(matched), 1)
            self.assertEqual(matched[0]["name"], "月订单数量")
        finally:
            engine.dispose()

    def test_fixed_filters_appended_to_formula(self):
        """指标固定筛选（如 order_status='delivered'）应拼进完整口径公式并随匹配结果返回。"""
        from app.core.metric_binding import match_metrics_from_question

        db, engine = self._session()
        try:
            db.add(
                self._metric(
                    "月订单数量",
                    "COUNT(orders.order_id)",
                    certification_status="certified",
                    calculation_config={
                        "filters": [
                            {
                                "logic": "AND",
                                "field": "orders.order_status",
                                "operator": "=",
                                "value": "delivered",
                            }
                        ]
                    },
                )
            )
            db.commit()
            datasource = SimpleNamespace(id=1)
            matched = match_metrics_from_question(
                db, "2018年8月的订单数量是多少，请参考月订单数量指标", datasource
            )
            self.assertEqual(
                matched[0]["formula"],
                "COUNT(orders.order_id) WHERE orders.order_status = 'delivered'",
            )
            self.assertEqual(matched[0]["filters"][0]["field"], "orders.order_status")
            self.assertEqual(matched[0]["filters"][0]["value"], "delivered")
        finally:
            engine.dispose()


class AgenticMetricConstraintTests(unittest.TestCase):
    """agentic 链路：目标指标公式约束与 repair 循环。"""

    def _datasource(self):
        return SimpleNamespace(
            name="Finance DS",
            source_type="database",
            database_url="sqlite:///:memory:",
            metadata_prompt="receivables(received_amount, receivable_amount)",
            schema_metadata=None,
            metrics_prompt="",
        )

    def test_agentic_validate_rejects_sql_missing_metric_formula(self):
        from app.core.agentic_nl2sql import _validate_agentic_sql

        metric_matches = [{"name": "回款率", "formula": "SUM(received_amount) / SUM(receivable_amount)"}]
        with self.assertRaises(ValueError) as ctx:
            _validate_agentic_sql(
                self._datasource(),
                "SELECT COUNT(*) AS pay_rate FROM receivables",
                question="查询回款率",
                plan={},
                metric_matches=metric_matches,
            )
        self.assertIn("未使用目标指标", str(ctx.exception))

    def test_agentic_validate_accepts_sql_using_metric_formula(self):
        from app.core.agentic_nl2sql import _validate_agentic_sql

        metric_matches = [{"name": "回款率", "formula": "SUM(received_amount) / SUM(receivable_amount)"}]
        sql = _validate_agentic_sql(
            self._datasource(),
            "SELECT SUM(received_amount) / SUM(receivable_amount) AS pay_rate FROM receivables",
            question="查询回款率",
            plan={},
            metric_matches=metric_matches,
        )
        self.assertIn("SUM(received_amount)", sql)

    def test_agentic_nl2sql_repairs_sql_not_using_target_metric_formula(self):
        from app.core.agentic_nl2sql import build_agentic_nl2sql

        metric_matches = [{"name": "回款率", "formula": "SUM(received_amount) / SUM(receivable_amount)"}]
        with patch(
            "app.core.agentic_nl2sql.chat_completion",
            new=AsyncMock(
                side_effect=[
                    '{"objective":"compute pay rate","steps":["aggregate"],"expected_output":"ratio"}',
                    "SELECT COUNT(*) AS pay_rate FROM receivables",
                    "SELECT SUM(received_amount) / SUM(receivable_amount) AS pay_rate FROM receivables",
                ]
            ),
        ) as mocked_chat:
            result = asyncio.run(
                build_agentic_nl2sql("查询回款率", self._datasource(), metric_matches=metric_matches)
            )

        self.assertEqual(mocked_chat.await_count, 3)
        self.assertIn("SUM(received_amount)", result["sql_query"])
        self.assertIn("sql_fix", [item["stage"] for item in result["trace"]])


if __name__ == "__main__":
    unittest.main()
