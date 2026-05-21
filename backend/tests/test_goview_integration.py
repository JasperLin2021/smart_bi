import asyncio
import json
import tempfile
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class GoViewIntegrationTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.audit_log import AuditLog
        from app.models.big_screen import BigScreen
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                AuditLog.__table__,
                BigScreen.__table__,
                DataSource.__table__,
            ],
        )
        return sessionmaker(bind=engine)()

    def _user(self, **overrides):
        values = {"id": 10, "username": "alice", "role": "org_admin", "org_id": 2}
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_user_launch_is_view_only(self):
        from app.api.goview import get_goview_launch
        from app.models.audit_log import AuditLog
        from app.models.organization import Organization

        db = self._db()
        db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
        db.commit()

        result = get_goview_launch(
            db=db,
            current_user=SimpleNamespace(id=10, username="alice", role="user", org_id=2),
        )

        self.assertEqual(result["modes"], ["view"])
        self.assertEqual(result["default_mode"], "view")
        self.assertNotIn("design", result["targets"])
        self.assertEqual(result["organization"]["id"], 2)
        self.assertEqual(db.query(AuditLog).filter(AuditLog.action == "goview.launch").count(), 1)

    def test_org_admin_launch_allows_design(self):
        from app.api.goview import get_goview_launch

        result = get_goview_launch(
            db=self._db(),
            current_user=SimpleNamespace(id=11, username="admin", role="org_admin", org_id=2),
        )

        self.assertEqual(result["modes"], ["view", "design"])
        self.assertIn("view", result["targets"])
        self.assertIn("design", result["targets"])

    def test_user_cannot_launch_design_mode(self):
        from app.api.goview import get_goview_launch
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            get_goview_launch(
                mode="design",
                db=self._db(),
                current_user=SimpleNamespace(id=10, username="alice", role="user", org_id=2),
            )

    def test_launch_token_is_scoped_to_goview_apis(self):
        from app.api.auth import get_current_user
        from app.api.goview import _goview_token, get_goview_current_user
        from app.models.organization import Organization
        from app.models.user import User
        from fastapi import HTTPException

        db = self._db()
        db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
        db.add(User(id=10, username="alice", hashed_password="x", role="org_admin", org_id=2))
        db.commit()

        token = _goview_token(
            SimpleNamespace(id=10, username="alice", role="org_admin", org_id=2),
            ["view", "design"],
            {"id": 2, "name": "Nexteer", "scope": "org"},
        )

        goview_user = get_goview_current_user(token=token, db=db)
        self.assertEqual(goview_user.username, "alice")
        with self.assertRaises(HTTPException):
            get_current_user(token=token, db=db)

    def test_launch_uses_request_host_for_browser_target_when_embed_is_loopback(self):
        from app.api import goview

        previous_base_url = goview.settings.goview_base_url
        previous_embed_base_url = goview.settings.goview_embed_base_url
        previous_reachable = goview._service_reachable
        try:
            goview.settings.goview_base_url = "http://127.0.0.1:3000"
            goview.settings.goview_embed_base_url = "http://127.0.0.1:3000"
            goview._service_reachable = lambda url: True
            request = SimpleNamespace(
                url=SimpleNamespace(scheme="http", hostname="127.0.0.1"),
                headers={"x-forwarded-host": "172.26.106.4:16057", "x-forwarded-proto": "http"},
            )

            result = goview.get_goview_launch(
                db=self._db(),
                current_user=SimpleNamespace(id=11, username="admin", role="org_admin", org_id=2),
                request=request,
            )

            self.assertTrue(result["targets"]["design"].startswith("http://172.26.106.4:3000/#/project/items"))
        finally:
            goview.settings.goview_base_url = previous_base_url
            goview.settings.goview_embed_base_url = previous_embed_base_url
            goview._service_reachable = previous_reachable

    def test_service_reachable_uses_html_request_and_accepts_spa_response(self):
        from app.api.goview import _service_reachable

        seen_accept_headers = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen_accept_headers.append(self.headers.get("Accept", ""))
                if "text/html" in seen_accept_headers[-1]:
                    self.send_response(200)
                else:
                    self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(_service_reachable(f"http://127.0.0.1:{server.server_port}/"))
            self.assertTrue(any("text/html" in value for value in seen_accept_headers))
        finally:
            server.shutdown()
            thread.join(timeout=1)
            server.server_close()

    def test_service_reachable_treats_client_error_as_reachable(self):
        from app.api.goview import _service_reachable

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(_service_reachable(f"http://127.0.0.1:{server.server_port}/missing"))
        finally:
            server.shutdown()
            thread.join(timeout=1)
            server.server_close()

    def test_project_lifecycle_uses_big_screen_records(self):
        from app.api import goview
        from app.models.big_screen import BigScreen
        from app.models.organization import Organization

        db = self._db()
        db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
        db.commit()
        user = self._user()

        created = goview.create_project(
            payload={"projectName": "销售大屏", "remarks": "月度经营", "indexImage": "thumb://a"},
            db=db,
            current_user=user,
        )

        self.assertEqual(created["code"], 200)
        screen_id = int(created["data"]["id"])
        screen = db.query(BigScreen).filter(BigScreen.id == screen_id).one()
        self.assertEqual(screen.title, "销售大屏")
        self.assertEqual(screen.org_id, 2)
        self.assertEqual(screen.owner_id, 10)

        saved = goview.save_project_data(
            projectId=str(screen_id),
            content=json.dumps({"componentList": [{"id": "chart-1"}]}, ensure_ascii=False),
            db=db,
            current_user=user,
        )
        self.assertEqual(saved["code"], 200)
        self.assertEqual(db.get(BigScreen, screen_id).canvas_json["componentList"][0]["id"], "chart-1")

        detail = goview.get_project_data(projectId=screen_id, db=db, current_user=user)
        self.assertEqual(detail["code"], 200)
        self.assertEqual(json.loads(detail["data"]["content"])["componentList"][0]["id"], "chart-1")

        listed = goview.list_projects(page=1, limit=10, db=db, current_user=user)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["data"][0]["projectName"], "销售大屏")
        self.assertEqual(listed["data"][0]["indexImage"], "thumb://a")

        published = goview.publish_project(id=screen_id, state=1, db=db, current_user=user)
        self.assertEqual(published["code"], 200)
        self.assertEqual(db.get(BigScreen, screen_id).status, "published")
        self.assertEqual(db.get(BigScreen, screen_id).visibility, "org")

        deleted = goview.delete_project(ids=str(screen_id), db=db, current_user=user)
        self.assertEqual(deleted["code"], 200)
        self.assertIsNone(db.get(BigScreen, screen_id))

    def test_smartbi_datasources_are_filtered_by_org(self):
        from app.api import goview
        from app.models.datasource import DataSource
        from app.models.organization import Organization

        db = self._db()
        db.add_all(
            [
                Organization(id=2, name="Nexteer", slug="nexteer"),
                Organization(id=3, name="Other", slug="other"),
                DataSource(
                    id=1,
                    name="当前组织",
                    slug="current",
                    database_url="sqlite:///current.db",
                    metadata_prompt="orders(id, amount)",
                    org_id=2,
                    is_active=1,
                ),
                DataSource(
                    id=2,
                    name="其他组织",
                    slug="other",
                    database_url="sqlite:///other.db",
                    metadata_prompt="orders(id, amount)",
                    org_id=3,
                    is_active=1,
                ),
            ]
        )
        db.commit()

        result = goview.list_smartbi_datasources(db=db, current_user=self._user(org_id=2))

        self.assertEqual(result["code"], 200)
        self.assertEqual([item["id"] for item in result["data"]], [1])

    def test_projects_are_filtered_by_org(self):
        from app.api import goview
        from app.models.big_screen import BigScreen
        from app.models.organization import Organization

        db = self._db()
        db.add_all(
            [
                Organization(id=2, name="Nexteer", slug="nexteer"),
                Organization(id=3, name="Other", slug="other"),
                BigScreen(
                    id=1,
                    title="当前组织大屏",
                    canvas_json={},
                    status="draft",
                    visibility="private",
                    org_id=2,
                    owner_id=10,
                ),
                BigScreen(
                    id=2,
                    title="其他组织大屏",
                    canvas_json={},
                    status="published",
                    visibility="org",
                    org_id=3,
                    owner_id=30,
                ),
            ]
        )
        db.commit()

        result = goview.list_projects(page=1, limit=10, db=db, current_user=self._user(org_id=2))

        self.assertEqual(result["count"], 1)
        self.assertEqual([item["id"] for item in result["data"]], [1])

    def test_smartbi_query_rejects_cross_org_datasource(self):
        from app.api import goview
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from fastapi import HTTPException

        db = self._db()
        db.add_all(
            [
                Organization(id=2, name="Nexteer", slug="nexteer"),
                Organization(id=3, name="Other", slug="other"),
                DataSource(
                    id=1,
                    name="其他组织库",
                    slug="other-sales",
                    database_url="sqlite:///other.db",
                    metadata_prompt="sales(region, amount)",
                    org_id=3,
                    is_active=1,
                ),
            ]
        )
        db.commit()

        with self.assertRaises(HTTPException):
            asyncio.run(
                goview.smartbi_query(
                    payload={"datasource_id": 1, "sql": "SELECT * FROM sales"},
                    db=db,
                    current_user=self._user(org_id=2),
                )
            )

    def test_smartbi_query_executes_select_against_accessible_datasource(self):
        from app.api import goview
        from app.models.datasource import DataSource
        from app.models.organization import Organization

        with tempfile.NamedTemporaryFile(suffix=".db") as database_file:
            engine = create_engine(f"sqlite:///{database_file.name}")
            with engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE sales (region TEXT, amount INTEGER)")
                conn.exec_driver_sql(
                    "INSERT INTO sales (region, amount) VALUES ('华东', 120), ('华南', 80)"
                )

            db = self._db()
            db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
            db.add(
                DataSource(
                    id=1,
                    name="销售库",
                    slug="sales",
                    database_url=f"sqlite:///{database_file.name}",
                    metadata_prompt="sales(region, amount)",
                    org_id=2,
                    is_active=1,
                )
            )
            db.commit()

            result = asyncio.run(
                goview.smartbi_query(
                    payload={
                        "datasource_id": 1,
                        "sql": "SELECT region, amount FROM sales ORDER BY amount DESC",
                    },
                    db=db,
                    current_user=self._user(org_id=2),
                )
            )

        self.assertEqual(result["code"], 200)
        self.assertEqual(result["data"]["columns"], ["region", "amount"])
        self.assertEqual(result["data"]["rows"][0], {"region": "华东", "amount": 120})
        self.assertEqual(result["data"]["dataset"]["dimensions"], ["region", "amount"])

    def test_smartbi_question_uses_agentic_query_mode(self):
        from app.api import goview
        from app.models.datasource import DataSource
        from app.models.organization import Organization

        db = self._db()
        db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
        db.add(
            DataSource(
                id=1,
                name="销售库",
                slug="sales",
                database_url="sqlite:///sales.db",
                metadata_prompt="sales(region, amount)",
                org_id=2,
                is_active=1,
            )
        )
        db.commit()
        captured = {}

        async def fake_ask(payload, db, current_user):
            captured["mode"] = payload.mode
            return {
                "result": {"columns": ["region"], "rows": [{"region": "华东"}]},
                "sql_query": "SELECT region FROM sales",
                "summary": "ok",
            }

        with patch.object(goview.query_api, "ask", new=fake_ask):
            result = asyncio.run(
                goview.smartbi_query(
                    payload={"datasource_id": 1, "question": "按区域统计"},
                    db=db,
                    current_user=self._user(org_id=2),
                )
            )

        self.assertEqual(captured["mode"], "agentic")
        self.assertEqual(result["code"], 200)
        self.assertEqual(result["data"]["columns"], ["region"])

    def test_smartbi_query_rejects_non_select_sql(self):
        from app.api import goview
        from app.models.datasource import DataSource
        from app.models.organization import Organization
        from fastapi import HTTPException

        db = self._db()
        db.add(Organization(id=2, name="Nexteer", slug="nexteer"))
        db.add(
            DataSource(
                id=1,
                name="销售库",
                slug="sales",
                database_url="sqlite:///sales.db",
                metadata_prompt="sales(region, amount)",
                org_id=2,
                is_active=1,
            )
        )
        db.commit()

        with self.assertRaises(HTTPException):
            asyncio.run(
                goview.smartbi_query(
                    payload={"datasource_id": 1, "sql": "DELETE FROM sales"},
                    db=db,
                    current_user=self._user(org_id=2),
                )
            )


if __name__ == "__main__":
    unittest.main()
