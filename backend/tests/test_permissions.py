import unittest
import sys
from types import SimpleNamespace

from fastapi import HTTPException


class PermissionResolverTests(unittest.TestCase):
    def test_user_model_exposes_permission_columns(self):
        from app.core.permissions import resolve_effective_permissions  # noqa: F401

        user_model = sys.modules["app.models.user"].User

        self.assertIn("data_scope", user_model.__table__.c)
        self.assertIn("permission_override_enabled", user_model.__table__.c)
        self.assertIn("menu_permissions", user_model.__table__.c)
        self.assertIn("action_permissions", user_model.__table__.c)

    def test_user_schema_exposes_permission_fields(self):
        from app.schemas.user import UserCreate, UserOut, UserUpdate

        payload = UserCreate(
            username="alice",
            password="secret",
            menu_permissions={"dashboard.view": True},
            action_permissions={"user.read": False},
        )

        self.assertEqual(payload.menu_permissions, {"dashboard.view": True})
        self.assertEqual(payload.action_permissions, {"user.read": False})

        for schema in (UserCreate, UserUpdate, UserOut):
            self.assertIn("data_scope", schema.model_fields)
            self.assertIn("permission_override_enabled", schema.model_fields)
            self.assertIn("menu_permissions", schema.model_fields)
            self.assertIn("action_permissions", schema.model_fields)

    def test_resolve_permissions_from_role_defaults(self):
        from app.core.permissions import ROLE_PERMISSION_TEMPLATES, resolve_effective_permissions

        user = SimpleNamespace(
            username="org-admin",
            hashed_password="hashed",
            role="org_admin",
            org_id=1,
            data_scope=None,
            permission_override_enabled=False,
            menu_permissions=None,
            action_permissions=None,
        )

        effective = resolve_effective_permissions(user)
        self.assertEqual(effective["data_scope"], ROLE_PERMISSION_TEMPLATES["org_admin"]["data_scope"])
        self.assertEqual(
            effective["menu_permissions"],
            ROLE_PERMISSION_TEMPLATES["org_admin"]["menu_permissions"],
        )
        self.assertEqual(
            effective["action_permissions"],
            ROLE_PERMISSION_TEMPLATES["org_admin"]["action_permissions"],
        )

    def test_user_overrides_replace_role_defaults(self):
        from app.core.permissions import resolve_effective_permissions

        user = SimpleNamespace(
            username="custom-user",
            hashed_password="hashed",
            role="org_admin",
            org_id=1,
            data_scope="owner",
            permission_override_enabled=True,
            menu_permissions={"llm_settings.view": True, "admin_console.view": False},
            action_permissions={"llm_settings.update": False, "user.permission.update": True},
        )

        effective = resolve_effective_permissions(user)
        self.assertEqual(effective["data_scope"], "owner")
        self.assertTrue(effective["menu_permissions"]["llm_settings.view"])
        self.assertFalse(effective["menu_permissions"]["admin_console.view"])
        self.assertFalse(effective["action_permissions"]["llm_settings.update"])
        self.assertTrue(effective["action_permissions"]["user.permission.update"])

    def test_super_admin_always_gets_full_access(self):
        from app.core.permissions import DATA_SCOPE_ALL, MENU_PERMISSION_KEYS, ACTION_PERMISSION_KEYS, resolve_effective_permissions

        user = SimpleNamespace(
            username="root",
            hashed_password="hashed",
            role="super_admin",
            org_id=None,
            data_scope="owner",
            permission_override_enabled=True,
            menu_permissions={"llm_settings.view": False},
            action_permissions={"user.read": False},
        )

        effective = resolve_effective_permissions(user)
        self.assertEqual(effective["data_scope"], DATA_SCOPE_ALL)
        self.assertTrue(all(effective["menu_permissions"][key] for key in MENU_PERMISSION_KEYS))
        self.assertTrue(all(effective["action_permissions"][key] for key in ACTION_PERMISSION_KEYS))

    def test_permission_helpers_check_decision_maps(self):
        from app.core.permissions import require_action, require_menu

        allowed_user = SimpleNamespace(
            role="org_admin",
            data_scope="org",
            permission_override_enabled=False,
            menu_permissions=None,
            action_permissions=None,
        )
        denied_user = SimpleNamespace(
            role="user",
            data_scope="owner",
            permission_override_enabled=True,
            menu_permissions={"llm_settings.view": False},
            action_permissions={"user.delete": False},
        )

        self.assertIs(require_menu(allowed_user, "dashboard.view"), allowed_user)
        self.assertIs(require_action(allowed_user, "user.read"), allowed_user)
        self.assertIs(require_menu(allowed_user, "goview.view"), allowed_user)
        self.assertIs(require_action(allowed_user, "goview.design"), allowed_user)

        with self.assertRaises(HTTPException):
            require_menu(denied_user, "llm_settings.view")
        with self.assertRaises(HTTPException):
            require_action(denied_user, "user.delete")


if __name__ == "__main__":
    unittest.main()
