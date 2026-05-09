import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class OrganizationDepartmentTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.audit_log import AuditLog
        from app.models.organization import Department, Organization
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                Department.__table__,
                User.__table__,
                AuditLog.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def _seed(self, db):
        from app.models.organization import Department, Organization
        from app.models.user import User

        lantu = Organization(id=1, name="蓝途科技", slug="lantu")
        galaxy = Organization(id=2, name="星河制造", slug="galaxy")
        db.add_all([lantu, galaxy])
        db.flush()

        sales = Department(id=10, name="销售中心", org_id=1, parent_id=None, sort_order=1)
        east = Department(id=11, name="华东销售组", org_id=1, parent_id=10, sort_order=1)
        quality = Department(id=20, name="质量管理部", org_id=2, parent_id=None, sort_order=1)
        db.add_all([sales, east, quality])
        db.flush()

        root = User(id=1, username="root", hashed_password="x", role="super_admin")
        lantu_admin = User(id=2, username="lantu.admin", hashed_password="x", role="org_admin", org_id=1)
        galaxy_admin = User(id=3, username="galaxy.admin", hashed_password="x", role="org_admin", org_id=2)
        lantu_sales = User(
            id=4,
            username="lantu.sales",
            hashed_password="x",
            role="user",
            org_id=1,
            department_id=10,
            department="销售中心",
        )
        lantu_ops = User(id=5, username="lantu.ops", hashed_password="x", role="user", org_id=1)
        db.add_all([root, lantu_admin, galaxy_admin, lantu_sales, lantu_ops])
        db.commit()
        return {
            "root": root,
            "lantu_admin": lantu_admin,
            "galaxy_admin": galaxy_admin,
            "lantu_sales": lantu_sales,
            "sales": sales,
            "east": east,
            "quality": quality,
        }

    def _assert_http(self, status_code, fn, *args, **kwargs):
        with self.assertRaises(HTTPException) as exc:
            fn(*args, **kwargs)
        self.assertEqual(exc.exception.status_code, status_code)
        return exc.exception

    def test_organization_tree_returns_nested_departments_and_user_counts(self):
        from app.api.organization import get_organization_tree

        db = self._db()
        data = self._seed(db)

        tree = get_organization_tree(db=db, current_user=data["root"])

        self.assertEqual([node["name"] for node in tree], ["蓝途科技", "星河制造"])
        lantu = tree[0]
        self.assertEqual(lantu["type"], "organization")
        self.assertEqual(lantu["department_count"], 2)
        self.assertEqual(lantu["user_count"], 3)
        self.assertEqual(lantu["children"][0]["name"], "销售中心")
        self.assertEqual(lantu["children"][0]["user_count"], 1)
        self.assertEqual(lantu["children"][0]["children"][0]["name"], "华东销售组")

        scoped_tree = get_organization_tree(db=db, current_user=data["lantu_admin"])
        self.assertEqual([node["slug"] for node in scoped_tree], ["lantu"])

    def test_department_crud_is_org_scoped_and_delete_is_reference_safe(self):
        from app.api.organization import create_department, delete_department, update_department
        from app.models.organization import Department
        from app.schemas.organization import DepartmentCreate, DepartmentUpdate

        db = self._db()
        data = self._seed(db)

        created = create_department(
            1,
            DepartmentCreate(name="销售运营组", parent_id=10),
            db=db,
            current_user=data["lantu_admin"],
        )
        self.assertEqual(created.name, "销售运营组")
        self.assertEqual(created.parent_id, 10)

        renamed = update_department(
            1,
            created.id,
            DepartmentUpdate(name="销售支持组"),
            db=db,
            current_user=data["lantu_admin"],
        )
        self.assertEqual(renamed.name, "销售支持组")

        cross_org = self._assert_http(
            403,
            create_department,
            2,
            DepartmentCreate(name="越权部门"),
            db=db,
            current_user=data["lantu_admin"],
        )
        self.assertIn("本企业", cross_org.detail)

        child_block = self._assert_http(
            409,
            delete_department,
            1,
            10,
            db=db,
            current_user=data["lantu_admin"],
        )
        self.assertIn("下级部门", child_block.detail)
        self.assertIn("用户", child_block.detail)

        delete_department(1, created.id, db=db, current_user=data["lantu_admin"])
        self.assertIsNone(db.query(Department).filter(Department.id == created.id).first())

    def test_user_creation_binds_to_department_entity_with_org_validation(self):
        from app.api.users import create_user
        from app.schemas.user import UserCreate

        db = self._db()
        data = self._seed(db)

        created = create_user(
            UserCreate(username="lantu.new.sales", password="x", role="user", org_id=1, department_id=10),
            db=db,
            current_user=data["lantu_admin"],
        )

        self.assertEqual(created["org_id"], 1)
        self.assertEqual(created["department_id"], 10)
        self.assertEqual(created["department"], "销售中心")

        cross_org = self._assert_http(
            400,
            create_user,
            UserCreate(username="lantu.bad.department", password="x", role="user", department_id=20),
            db=db,
            current_user=data["lantu_admin"],
        )
        self.assertIn("部门不属于所选企业", cross_org.detail)


if __name__ == "__main__":
    unittest.main()
