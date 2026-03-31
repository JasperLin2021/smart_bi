import unittest

from app.schemas.datasource import ColumnSchema, RelationshipSchema, SchemaMetadata, TableSchema


class DrillConfigGenerationTests(unittest.TestCase):
    def _build_schema(self) -> SchemaMetadata:
        return SchemaMetadata(
            tables=[
                TableSchema(
                    name="mainrecord",
                    description="班次主数据",
                    columns=[
                        ColumnSchema(name="ID", type="VARCHAR"),
                        ColumnSchema(name="LINE", type="VARCHAR"),
                        ColumnSchema(name="SHIFTNAME", type="VARCHAR"),
                        ColumnSchema(name="PARTNO", type="VARCHAR"),
                        ColumnSchema(name="SHIFTSTARTTIME", type="DATETIME"),
                        ColumnSchema(name="OEE", type="FLOAT"),
                        ColumnSchema(name="RTY", type="FLOAT"),
                        ColumnSchema(name="TOTALCOUNT", type="INTEGER"),
                    ],
                ),
                TableSchema(
                    name="ngtype",
                    description="失效详情",
                    columns=[
                        ColumnSchema(name="ID", type="VARCHAR"),
                        ColumnSchema(name="MAINID", type="VARCHAR"),
                        ColumnSchema(name="LINE", type="VARCHAR"),
                        ColumnSchema(name="NGTYPE", type="VARCHAR"),
                        ColumnSchema(name="STN", type="VARCHAR"),
                        ColumnSchema(name="NGCOUNT", type="INTEGER"),
                        ColumnSchema(name="STNCOUNT", type="INTEGER"),
                    ],
                ),
                TableSchema(
                    name="rtyinfo",
                    description="各工站投入产出详情",
                    columns=[
                        ColumnSchema(name="ID", type="VARCHAR"),
                        ColumnSchema(name="MAINID", type="VARCHAR"),
                        ColumnSchema(name="OP", type="VARCHAR"),
                        ColumnSchema(name="STN", type="VARCHAR"),
                        ColumnSchema(name="TOTAL", type="INTEGER"),
                        ColumnSchema(name="NGCOUNT", type="INTEGER"),
                        ColumnSchema(name="OKCOUNT", type="INTEGER"),
                        ColumnSchema(name="H07", type="VARCHAR"),
                    ],
                ),
            ],
            relationships=[
                RelationshipSchema(
                    from_table="ngtype",
                    from_column="MAINID",
                    to_table="mainrecord",
                    to_column="ID",
                ),
                RelationshipSchema(
                    from_table="rtyinfo",
                    from_column="MAINID",
                    to_table="mainrecord",
                    to_column="ID",
                ),
            ],
        )

    def test_generate_candidates_from_schema(self):
        from app.core.drill_config import generate_drill_config

        config = generate_drill_config(self._build_schema())

        dimension_ids = {item["id"] for item in config["dimensions"]}
        metric_ids = {item["id"] for item in config["metrics"]}
        path_ids = {item["id"] for item in config["paths"]}

        self.assertIn("mainrecord.line", dimension_ids)
        self.assertIn("mainrecord.shiftstarttime", dimension_ids)
        self.assertIn("ngtype.ngtype", dimension_ids)
        self.assertIn("mainrecord.totalcount", metric_ids)
        self.assertIn("ngtype.ngcount", metric_ids)
        self.assertIn("mainrecord.line__ngtype.ngtype", path_ids)
        self.assertIn("mainrecord.line__rtyinfo.op", path_ids)
        self.assertNotIn("rtyinfo.h07", dimension_ids)

    def test_generated_paths_include_human_labels(self):
        from app.core.drill_config import generate_drill_config

        config = generate_drill_config(self._build_schema())
        paths = {item["id"]: item for item in config["paths"]}

        self.assertEqual(paths["mainrecord.line__ngtype.ngtype"]["label"], "看不良类型分布")
        self.assertEqual(paths["mainrecord.line__rtyinfo.op"]["label"], "看工序明细")


if __name__ == "__main__":
    unittest.main()
