import asyncio
import unittest
from unittest.mock import AsyncMock, patch


class AgentPlannerSkillTests(unittest.TestCase):
    def test_llm_only_mode_skips_heuristics(self):
        from app.core.agent_planner import plan_agent_actions

        context = {
            "current_route": "/dashboard",
            "current_datasource_id": None,
            "current_datasource_name": None,
            "datasource_names": [],
            "allowed_routes": ["/dashboard", "/datasource-settings"],
            "allowed_actions": [{"type": "navigate"}],
            "skills": [{"name": "navigation", "allowed_actions": ["navigate"], "source": "builtin"}],
            "agent_planner_mode": "llm_only",
        }

        llm_reply = """
        {
          "reply": "由 LLM 规划跳转。",
          "reasoning": "测试返回",
          "missing_fields": [],
          "actions": [
            {
              "type": "navigate",
              "label": "打开数据源管理",
              "params": {"route": "/datasource-settings"}
            }
          ]
        }
        """

        with patch("app.core.agent_planner.chat_completion", new=AsyncMock(return_value=llm_reply)) as mocked:
            result = asyncio.run(plan_agent_actions("打开数据源管理", context))

        mocked.assert_awaited()
        self.assertEqual(result["reply"], "由 LLM 规划跳转。")
        self.assertEqual(result["actions"][0]["type"], "navigate")

    def test_install_skill_request_generates_install_action(self):
        from app.core.agent_planner import build_agent_context, plan_agent_actions

        context = build_agent_context(
            role="super_admin",
            route="/dashboard",
            datasource_id=None,
            datasource_name=None,
            datasource_names=[],
            agent_planner_mode="heuristic_then_llm",
        )

        result = asyncio.run(
            plan_agent_actions(
                "安装 https://github.com/anthropics/skills/tree/main/skills/skill-creator 这个 skill",
                context,
            )
        )

        self.assertEqual(result["skill"]["name"], "skill_admin")
        self.assertEqual(len(result["actions"]), 1)
        self.assertEqual(result["actions"][0]["type"], "install_agent_skill")
        self.assertEqual(
            result["actions"][0]["params"]["source"],
            "https://github.com/anthropics/skills/tree/main/skills/skill-creator",
        )
        self.assertTrue(result["requires_confirmation"])

    def test_install_skill_request_trims_chinese_suffix(self):
        from app.core.agent_planner import build_agent_context, plan_agent_actions

        context = build_agent_context(
            role="super_admin",
            route="/dashboard",
            datasource_id=None,
            datasource_name=None,
            datasource_names=[],
            agent_planner_mode="heuristic_then_llm",
        )

        result = asyncio.run(
            plan_agent_actions(
                "安装https://github.com/anthropics/skills/tree/main/skills/skill-creator这个skill",
                context,
            )
        )

        self.assertEqual(
            result["actions"][0]["params"]["source"],
            "https://github.com/anthropics/skills/tree/main/skills/skill-creator",
        )


if __name__ == "__main__":
    unittest.main()
