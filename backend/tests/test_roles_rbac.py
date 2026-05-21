import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class RoleRbacTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.audit_log import AuditLog
        from app.models.organization import Department, Organization
        from app.models.role import Role
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                Department.__table__,
                Role.__table__,
                User.__table__,
                AuditLog.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def _seed(self, db):
        from app.models.organization import Department, Organization
        from app.models.user import User

        org = Organization(id=1, name="蓝途科技", slug="lantu")
        other_org = Organization(id=2, name="星河制造", slug="galaxy")
        sales = Department(id=10, name="销售中心", org_id=1, parent_id=None, sort_order=1)
        root = User(id=1, username="root", hashed_password="x", role="super_admin")
        org_admin = User(id=2, username="lantu.admin", hashed_password="x", role="org_admin", org_id=1)
        limited_admin = User(
            id=3,
            username="lantu.limited",
            hashed_password="x",
            role="org_admin",
            org_id=1,
            permission_override_enabled=True,
            action_permissions='{"user.create": false}',
        )
        db.add_all([org, other_org, sales, root, org_admin, limited_admin])
        db.commit()
        return {"root": root, "org_admin": org_admin, "limited_admin": limited_admin, "sales": sales}

    def _assert_http(self, status_code, fn, *args, **kwargs):
        with self.assertRaises(HTTPException) as exc:
            fn(*args, **kwargs)
        self.assertEqual(exc.exception.status_code, status_code)
        return exc.exception

    def test_role_crud_is_scoped_and_builtin_roles_are_read_only(self):
        from app.api.roles import create_role, delete_role, list_assignable_roles, list_roles, update_role
        from app.schemas.role import RoleCreate, RoleUpdate

        db = self._db()
        data = self._seed(db)

        created = create_role(
            RoleCreate(
                code="sales_analyst",
                name="销售分析师",
                description="销售部门分析岗位",
                menu_permissions={"dashboard.view": True, "admin_console.view": False},
                action_permissions={"dashboard.read": True, "user.read": False},
            ),
            db=db,
            current_user=data["org_admin"],
        )
        self.assertEqual(created["org_id"], 1)
        self.assertFalse(created["is_builtin"])

        roles = list_roles(db=db, current_user=data["org_admin"])
        self.assertIn("sales_analyst", {role["code"] for role in roles})
        self.assertTrue(next(role for role in roles if role["code"] == "org_admin")["is_builtin"])

        renamed = update_role(
            created["id"],
            RoleUpdate(name="销售经营分析师", action_permissions={"dashboard.read": True}),
            db=db,
            current_user=data["org_admin"],
        )
        self.assertEqual(renamed["name"], "销售经营分析师")

        self._assert_http(
            403,
            update_role,
            0,
            RoleUpdate(name="不能改内置角色"),
            db=db,
            current_user=data["org_admin"],
        )

        assignable = list_assignable_roles(db=db, current_user=data["org_admin"])
        self.assertIn("sales_analyst", {role["code"] for role in assignable})
        self.assertNotIn("org_admin", {role["code"] for role in assignable})
        self.assertNotIn("super_admin", {role["code"] for role in assignable})

        delete_role(created["id"], db=db, current_user=data["org_admin"])
        roles_after_delete = list_roles(db=db, current_user=data["org_admin"])
        self.assertNotIn("sales_analyst", {role["code"] for role in roles_after_delete})

    def test_user_management_honors_action_permissions_and_assignable_roles(self):
        from app.api.users import create_user
        from app.schemas.user import UserCreate

        db = self._db()
        data = self._seed(db)

        self._assert_http(
            403,
            create_user,
            UserCreate(username="blocked.user", password="x", role="user", org_id=1),
            db=db,
            current_user=data["limited_admin"],
        )

        self._assert_http(
            403,
            create_user,
            UserCreate(username="new.org.admin", password="x", role="org_admin", org_id=1),
            db=db,
            current_user=data["org_admin"],
        )

        data["org_admin"].permission_override_enabled = True
        data["org_admin"].action_permissions = '{"user.assign_org_admin": true}'
        db.commit()
        created = create_user(
            UserCreate(username="new.org.admin", password="x", role="org_admin", org_id=1),
            db=db,
            current_user=data["org_admin"],
        )
        self.assertEqual(created["role"], "org_admin")


if __name__ == "__main__":
    unittest.main()
