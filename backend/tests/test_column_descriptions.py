import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.schemas.datasource import ColumnSchema, TableSchema


class ColumnDescriptionTests(unittest.TestCase):
    def test_generate_column_descriptions_only_fills_blanks(self):
        from app.core.schema_enrichment import generate_column_descriptions

        table = TableSchema(
            name="ngtype",
            description="失效详情",
            columns=[
                ColumnSchema(name="LINE", type="VARCHAR", description="产线"),
                ColumnSchema(name="NGTYPE", type="VARCHAR", description=None),
                ColumnSchema(name="NGCOUNT", type="INTEGER", description=None),
            ],
        )

        raw = """
        {
          "descriptions": {
            "NGTYPE": "不良类型",
            "NGCOUNT": "不良数量",
            "LINE": "不应覆盖"
          }
        }
        """

        with patch("app.core.schema_enrichment.chat_completion", new=AsyncMock(return_value=raw)):
            enriched, filled_count = asyncio.run(generate_column_descriptions("Nexteer", table))

        self.assertEqual(filled_count, 2)
        self.assertEqual(enriched.columns[0].description, "产线")
        self.assertEqual(enriched.columns[1].description, "不良类型")
        self.assertEqual(enriched.columns[2].description, "不良数量")

    def test_generate_column_descriptions_returns_original_when_no_blanks(self):
        from app.core.schema_enrichment import generate_column_descriptions

        table = TableSchema(
            name="ngtype",
            description="失效详情",
            columns=[ColumnSchema(name="LINE", type="VARCHAR", description="产线")],
        )

        enriched, filled_count = asyncio.run(generate_column_descriptions("Nexteer", table))

        self.assertEqual(filled_count, 0)
        self.assertEqual(enriched.columns[0].description, "产线")


if __name__ == "__main__":
    unittest.main()
