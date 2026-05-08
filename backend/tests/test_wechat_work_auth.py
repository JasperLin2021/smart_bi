import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeHttpClient:
    def __init__(self, responses, calls):
        self.responses = responses
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, params=None):
        self.calls.append(("GET", url, params))
        return _FakeResponse(self.responses.pop(0))

    def post(self, url, json=None, params=None):
        self.calls.append(("POST", url, params, json))
        return _FakeResponse(self.responses.pop(0))


class WechatWorkClientTests(unittest.TestCase):
    def test_login_url_contains_corp_agent_redirect_and_state(self):
        from app.core.wechat_work import WechatWorkClient

        client = WechatWorkClient(
            corp_id="corp-1",
            agent_id="1000002",
            app_secret="secret",
            callback_url="https://bi.example.com/api/auth/wechat-work/callback",
        )

        url = client.build_login_url("state-1")

        self.assertIn("https://open.weixin.qq.com/connect/oauth2/authorize", url)
        self.assertIn("appid=corp-1", url)
        self.assertIn("agentid=1000002", url)
        self.assertIn("state=state-1", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fbi.example.com%2Fapi%2Fauth%2Fwechat-work%2Fcallback", url)
        self.assertTrue(url.endswith("#wechat_redirect"))

    def test_token_user_and_message_calls_parse_wechat_payloads(self):
        from app.core.wechat_work import WechatWorkClient

        calls = []
        responses = [
            {"errcode": 0, "access_token": "token-1"},
            {"errcode": 0, "UserId": "zhangsan"},
            {
                "errcode": 0,
                "userid": "zhangsan",
                "name": "张三",
                "email": "zhangsan@example.com",
                "mobile": "13800000000",
                "department": [7, 9],
            },
            {"errcode": 0},
        ]

        def fake_client(*args, **kwargs):
            return _FakeHttpClient(responses, calls)

        client = WechatWorkClient(
            corp_id="corp-1",
            agent_id="1000002",
            app_secret="secret",
            callback_url="https://bi.example.com/callback",
        )

        with patch("app.core.wechat_work.httpx.Client", fake_client):
            token = client.get_access_token()
            user_id = client.get_user_id_by_code("code-1", token)
            user = client.get_user(token, user_id)
            client.send_textcard(token, "zhangsan", "行动项提醒", "请处理异常工单", "https://bi.example.com/action-items")

        self.assertEqual(token, "token-1")
        self.assertEqual(user_id, "zhangsan")
        self.assertEqual(user.user_id, "zhangsan")
        self.assertEqual(user.name, "张三")
        self.assertEqual(user.department_ids, ["7", "9"])

        self.assertEqual(calls[0][0], "GET")
        self.assertIn("/cgi-bin/gettoken", calls[0][1])
        self.assertEqual(calls[0][2]["corpid"], "corp-1")
        self.assertEqual(calls[1][2]["code"], "code-1")

        send_call = calls[3]
        self.assertEqual(send_call[0], "POST")
        self.assertIn("/cgi-bin/message/send", send_call[1])
        self.assertEqual(send_call[3]["touser"], "zhangsan")
        self.assertEqual(send_call[3]["msgtype"], "textcard")
        self.assertEqual(send_call[3]["agentid"], "1000002")

    def test_wechat_error_payload_raises_value_error(self):
        from app.core.wechat_work import WechatWorkClient

        calls = []

        def fake_client(*args, **kwargs):
            return _FakeHttpClient([{"errcode": 40014, "errmsg": "invalid access token"}], calls)

        client = WechatWorkClient(
            corp_id="corp-1",
            agent_id="1000002",
            app_secret="secret",
            callback_url="https://bi.example.com/callback",
        )

        with patch("app.core.wechat_work.httpx.Client", fake_client):
            with self.assertRaises(ValueError) as ctx:
                client.get_access_token()

        self.assertIn("invalid access token", str(ctx.exception))


class _FakeWechatWorkClient:
    def __init__(self, external_user):
        self.external_user = external_user

    def build_login_url(self, state):
        return f"https://wechat.example.com/oauth?state={state}"

    def get_access_token(self):
        return "token-1"

    def get_user_id_by_code(self, code, access_token):
        return self.external_user.user_id

    def get_user(self, access_token, user_id):
        return self.external_user


class WechatWorkAuthFlowTests(unittest.TestCase):
    def _db(self):
        from app.db.base_class import Base
        from app.models.integration import (
            ExternalIdentity,
            ExternalOrgBinding,
            ExternalPermissionMapping,
            IntegrationConfig,
            MessageDelivery,
        )
        from app.models.organization import Organization
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            bind=engine,
            tables=[
                Organization.__table__,
                User.__table__,
                IntegrationConfig.__table__,
                ExternalOrgBinding.__table__,
                ExternalIdentity.__table__,
                ExternalPermissionMapping.__table__,
                MessageDelivery.__table__,
            ],
        )
        db = sessionmaker(bind=engine)()
        db.add(Organization(id=2, name="嘉盛半导体", slug="carsem"))
        db.commit()
        return db

    def _seed_config(self, db):
        from app.models.integration import IntegrationConfig

        db.add(
            IntegrationConfig(
                provider="wechat_work",
                name="企业微信",
                enabled=True,
                corp_id="corp-1",
                agent_id="1000002",
                app_secret="secret-1",
                callback_url="https://bi.example.com/api/auth/wechat-work/callback",
            )
        )
        db.commit()

    def test_login_url_requires_enabled_wechat_config(self):
        from app.api.auth import get_wechat_work_login_url

        db = self._db()
        with self.assertRaises(HTTPException) as ctx:
            get_wechat_work_login_url(db=db)

        self.assertEqual(ctx.exception.status_code, 400)

    def test_callback_rejects_unbound_corp(self):
        from app.api.auth import wechat_work_callback
        from app.core.wechat_work import WechatWorkUser

        db = self._db()
        self._seed_config(db)
        fake_client = _FakeWechatWorkClient(
            WechatWorkUser(user_id="zhangsan", name="张三", department_ids=["7"])
        )

        with patch("app.api.auth._build_wechat_work_client", return_value=fake_client):
            with self.assertRaises(HTTPException) as ctx:
                wechat_work_callback(code="code-1", state="state-1", db=db)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_callback_auto_creates_user_and_identity_for_bound_corp(self):
        from app.api.auth import wechat_work_callback
        from app.core.wechat_work import WechatWorkUser
        from app.models.integration import ExternalIdentity, ExternalOrgBinding
        from app.models.user import User

        db = self._db()
        self._seed_config(db)
        db.add(ExternalOrgBinding(provider="wechat_work", external_corp_id="corp-1", org_id=2))
        db.commit()
        fake_client = _FakeWechatWorkClient(
            WechatWorkUser(
                user_id="zhangsan",
                name="张三",
                email="zhangsan@example.com",
                mobile="13800000000",
                department_ids=["7"],
            )
        )

        with patch("app.api.auth._build_wechat_work_client", return_value=fake_client):
            response = wechat_work_callback(code="code-1", state="state-1", db=db)

        user = db.query(User).filter(User.username == "ww:corp-1:zhangsan").one()
        identity = db.query(ExternalIdentity).one()
        self.assertEqual(user.role, "user")
        self.assertEqual(user.org_id, 2)
        self.assertEqual(identity.user_id, user.id)
        self.assertEqual(identity.display_name, "张三")
        self.assertIn("smart-bi-token", response.body.decode("utf-8"))

    def test_callback_applies_department_permission_mapping(self):
        from app.api.auth import wechat_work_callback
        from app.core.wechat_work import WechatWorkUser
        from app.models.integration import ExternalOrgBinding, ExternalPermissionMapping
        from app.models.user import User

        db = self._db()
        self._seed_config(db)
        db.add(ExternalOrgBinding(provider="wechat_work", external_corp_id="corp-1", org_id=2))
        db.add(
            ExternalPermissionMapping(
                provider="wechat_work",
                external_corp_id="corp-1",
                external_department_id="7",
                org_id=2,
                role="org_admin",
                data_scope="org",
                menu_permissions='{"dashboard.view": true}',
                action_permissions='{"dashboard.read": true}',
                priority=10,
                enabled=True,
            )
        )
        db.add(
            ExternalPermissionMapping(
                provider="wechat_work",
                external_corp_id="corp-1",
                external_department_id="9",
                org_id=2,
                role="super_admin",
                priority=1,
                enabled=True,
            )
        )
        db.commit()
        fake_client = _FakeWechatWorkClient(
            WechatWorkUser(user_id="lisi", name="李四", department_ids=["7", "9"])
        )

        with patch("app.api.auth._build_wechat_work_client", return_value=fake_client):
            wechat_work_callback(code="code-1", state="state-1", db=db)

        user = db.query(User).filter(User.username == "ww:corp-1:lisi").one()
        self.assertEqual(user.role, "org_admin")
        self.assertEqual(user.data_scope, "org")
        self.assertTrue(user.permission_override_enabled)
        self.assertEqual(user.menu_permissions, '{"dashboard.view": true}')
        self.assertEqual(user.action_permissions, '{"dashboard.read": true}')
