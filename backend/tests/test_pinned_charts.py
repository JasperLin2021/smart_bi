import unittest
from types import SimpleNamespace
from unittest.mock import patch


class PinnedChartsTests(unittest.TestCase):
    def test_create_pinned_chart_defaults_to_active_datasource_when_missing(self):
        from app.models.organization import Organization  # noqa: F401
        from app.api.pinned_charts import PinnedChartCreate, create_pinned_chart

        created = {}
        active_datasource = SimpleNamespace(id=2, is_active=1)

        class FakeQuery:
            def __init__(self, model):
                self.model = model

            def filter(self, *_args, **_kwargs):
                return self

            def count(self):
                return 0

            def first(self):
                if self.model.__name__ == "DataSource":
                    return active_datasource
                return None

        class FakeDb:
            def query(self, model):
                return FakeQuery(model)

            def add(self, row):
                created["row"] = row

            def commit(self):
                return None

            def refresh(self, row):
                row.id = 1

        payload = PinnedChartCreate(
            title="测试图表",
            description=None,
            sql_query="select 1",
            chart_type="bar",
            sort_order="desc",
            datasource_id=None,
        )

        result = create_pinned_chart(
            payload,
            db=FakeDb(),
            current_user=SimpleNamespace(id=10),
        )

        self.assertEqual(created["row"].datasource_id, 2)
        self.assertEqual(result.datasource_id, 2)

    def test_list_pinned_charts_with_data_uses_excel_executor_for_excel_datasource(self):
        from app.api.pinned_charts import list_pinned_charts_with_data
        from app.models.datasource import DataSource
        from app.models.pinned_chart import PinnedChart

        chart = SimpleNamespace(
            id=3,
            user_id=10,
            datasource_id=2,
            title="产出最高的前5个单元",
            description=None,
            chart_type="pie",
            sort_order="desc",
            sql_query="select 1",
            display_order=0,
        )
        datasource = SimpleNamespace(
            id=2,
            source_type="excel",
            database_url="/tmp/fake.xlsx",
        )

        class FakePinnedQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def all(self):
                return [chart]

        class FakeDatasourceQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return datasource

        class FakeDb:
            def query(self, model):
                if model is PinnedChart:
                    return FakePinnedQuery()
                if model is DataSource:
                    return FakeDatasourceQuery()
                raise AssertionError(f"unexpected model: {model}")

        with patch(
            "app.api.pinned_charts.execute_excel_query",
            return_value={"columns": ["LINE", "total_output"], "rows": [{"LINE": "A", "total_output": 10}]},
        ) as mocked_execute:
            result = list_pinned_charts_with_data(
                datasource_id=2,
                db=FakeDb(),
                current_user=SimpleNamespace(id=10),
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rows"][0]["LINE"], "A")
        mocked_execute.assert_called_once_with("/tmp/fake.xlsx", "select 1")

    def test_preview_pinned_chart_executes_sql_without_saving_chart(self):
        from app.api.pinned_charts import PinnedChartPreviewRequest, preview_pinned_chart
        from app.models.datasource import DataSource
        from app.models.pinned_chart import PinnedChart

        datasource = SimpleNamespace(
            id=2,
            source_type="excel",
            database_url="/tmp/fake.xlsx",
        )

        class FakeDatasourceQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return datasource

        class FakeChartQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def count(self):
                return 0

        class FakeDb:
            def __init__(self):
                self.added = []

            def query(self, model):
                if model is DataSource:
                    return FakeDatasourceQuery()
                if model is PinnedChart:
                    return FakeChartQuery()
                raise AssertionError(f"unexpected model: {model}")

            def add(self, row):
                self.added.append(row)

        db = FakeDb()
        with patch(
            "app.api.pinned_charts.execute_excel_query",
            return_value={"columns": ["LINE", "total_output"], "rows": [{"LINE": "A", "total_output": 10}]},
        ) as mocked_execute:
            result = preview_pinned_chart(
                PinnedChartPreviewRequest(sql_query="select * from Sheet1", datasource_id=2),
                db=db,
                current_user=SimpleNamespace(id=10),
            )

        self.assertEqual(result.columns, ["LINE", "total_output"])
        self.assertEqual(result.rows, [{"LINE": "A", "total_output": 10}])
        self.assertEqual(db.added, [])
        mocked_execute.assert_called_once_with("/tmp/fake.xlsx", "select * from Sheet1")


if __name__ == "__main__":
    unittest.main()
