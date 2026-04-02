import unittest


class AgentActionPolicyTests(unittest.TestCase):
    def test_org_admin_cannot_manage_organizations(self):
        from app.core.agent_actions import get_action_catalog

        catalog = get_action_catalog("org_admin")
        action_types = {item["type"] for item in catalog}
        self.assertNotIn("create_organization", action_types)
        self.assertNotIn("delete_organization", action_types)

    def test_delete_actions_require_confirmation(self):
        from app.core.agent_actions import ACTION_SPECS

        self.assertEqual(ACTION_SPECS["delete_user"]["risk"], "high")
        self.assertEqual(ACTION_SPECS["delete_datasource"]["risk"], "high")
        self.assertEqual(ACTION_SPECS["delete_metric"]["risk"], "high")

    def test_safe_query_action_available_for_basic_user(self):
        from app.core.agent_actions import get_action_catalog

        catalog = get_action_catalog("user")
        action_types = {item["type"] for item in catalog}
        self.assertIn("navigate", action_types)
        self.assertIn("switch_datasource", action_types)
        self.assertIn("ask_query", action_types)
        self.assertNotIn("create_user", action_types)

    def test_basic_user_routes_are_limited(self):
        from app.core.agent_planner import build_agent_context

        context = build_agent_context(
            role="user",
            route="/dashboard",
            datasource_id=None,
            datasource_name=None,
            datasource_names=[],
        )

        self.assertIn("/smart-query", context["allowed_routes"])
        self.assertNotIn("/org-management", context["allowed_routes"])
        self.assertNotIn("/llm-settings", context["allowed_routes"])

    def test_super_admin_can_install_agent_skill(self):
        from app.core.agent_actions import get_action_catalog

        catalog = get_action_catalog("super_admin")
        action_types = {item["type"] for item in catalog}
        self.assertIn("install_agent_skill", action_types)

    def test_basic_user_cannot_install_agent_skill(self):
        from app.core.agent_actions import get_action_catalog

        catalog = get_action_catalog("user")
        action_types = {item["type"] for item in catalog}
        self.assertNotIn("install_agent_skill", action_types)


if __name__ == "__main__":
    unittest.main()
