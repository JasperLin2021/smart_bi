import unittest


class DrillRuntimeTests(unittest.TestCase):
    def test_build_drill_actions_from_result(self):
        from app.core.drill_runtime import build_drill_actions

        config = {
            "dimensions": [
                {"id": "mainrecord.line", "table": "mainrecord", "column": "LINE", "label": "产线", "kind": "line", "enabled": True},
                {"id": "ngtype.ngtype", "table": "ngtype", "column": "NGTYPE", "label": "异常类型", "kind": "ng", "enabled": True},
                {"id": "rtyinfo.op", "table": "rtyinfo", "column": "OP", "label": "工序", "kind": "station", "enabled": True},
            ],
            "metrics": [],
            "paths": [
                {
                    "id": "mainrecord.line__ngtype.ngtype",
                    "source_dimension_id": "mainrecord.line",
                    "target_dimension_id": "ngtype.ngtype",
                    "label": "看不良类型分布",
                    "action": "group_by",
                    "enabled": True,
                },
                {
                    "id": "mainrecord.line__rtyinfo.op",
                    "source_dimension_id": "mainrecord.line",
                    "target_dimension_id": "rtyinfo.op",
                    "label": "看工序明细",
                    "action": "group_by",
                    "enabled": True,
                },
            ],
        }

        actions = build_drill_actions(
            config=config,
            columns=["LINE", "TOTALCOUNT", "OEE"],
            row={"LINE": "REPS3 BSI", "TOTALCOUNT": 1866, "OEE": 75.8},
        )

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["source_value"], "REPS3 BSI")
        self.assertEqual(actions[0]["question"], "只看产线为 REPS3 BSI 的数据，按异常类型继续分析。")

    def test_skip_disabled_and_unknown_paths(self):
        from app.core.drill_runtime import build_drill_actions

        config = {
            "dimensions": [
                {"id": "mainrecord.line", "table": "mainrecord", "column": "LINE", "label": "产线", "kind": "line", "enabled": True},
                {"id": "ngtype.ngtype", "table": "ngtype", "column": "NGTYPE", "label": "异常类型", "kind": "ng", "enabled": False},
            ],
            "metrics": [],
            "paths": [
                {
                    "id": "mainrecord.line__ngtype.ngtype",
                    "source_dimension_id": "mainrecord.line",
                    "target_dimension_id": "ngtype.ngtype",
                    "label": "看不良类型分布",
                    "action": "group_by",
                    "enabled": True,
                }
            ],
        }

        actions = build_drill_actions(
            config=config,
            columns=["LINE", "TOTALCOUNT"],
            row={"LINE": "REPS3 BSI", "TOTALCOUNT": 1866},
        )

        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
