import unittest


class AgentSkillSelectionTests(unittest.TestCase):
    def test_query_skill_limits_actions(self):
        from app.core.agent_planner import apply_skill_action_constraints

        actions = [
            {"type": "ask_query", "label": "执行智能问数", "risk": "low", "params": {}},
            {"type": "delete_user", "label": "删除用户", "risk": "high", "params": {}},
        ]
        skill = {
            "name": "query_analysis",
            "allowed_actions": ["ask_query", "navigate", "switch_datasource"],
        }

        filtered = apply_skill_action_constraints(actions, skill)
        self.assertEqual([item["type"] for item in filtered], ["ask_query"])


if __name__ == "__main__":
    unittest.main()
