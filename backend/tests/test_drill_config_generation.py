import unittest


class DrillConfigGenerationTests(unittest.TestCase):
    def test_ng_dimension_can_drill_into_station_dimension(self):
        from app.core.drill_config import generate_drill_config
        from app.schemas.datasource import ColumnSchema, SchemaMetadata, TableSchema

        schema = SchemaMetadata(
            tables=[
                TableSchema(
                    name="ngtype",
                    description="失效详情",
                    columns=[
                        ColumnSchema(name="LINE", type="VARCHAR"),
                        ColumnSchema(name="NGTYPE", type="VARCHAR"),
                        ColumnSchema(name="STN", type="VARCHAR"),
                        ColumnSchema(name="NGCOUNT", type="INTEGER"),
                    ],
                )
            ],
            relationships=[],
        )

        config = generate_drill_config(schema)
        path_ids = {item["id"] for item in config["paths"]}

        self.assertIn("ngtype.ngtype__ngtype.stn", path_ids)


if __name__ == "__main__":
    unittest.main()
