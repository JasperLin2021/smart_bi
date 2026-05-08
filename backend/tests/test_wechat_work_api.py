import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class WechatWorkIntegrationApiTests(unittest.TestCase):
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
        db.add(User(id=8, username="ww-user", hashed_password="x", role="user", org_id=2))
        db.commit()
        return db

    def _admin(self):
        return SimpleNamespace(id=1, username="admin", role="super_admin", org_id=None)

    def test_config_save_read_does_not_expose_secret(self):
        from app.api.integrations import get_wechat_work_config, update_wechat_work_config
        from app.models.integration import IntegrationConfig
        from app.schemas.integration import WechatWorkConfigUpdate

        db = self._db()
        response = update_wechat_work_config(
            WechatWorkConfigUpdate(
                enabled=True,
                corp_id="corp-1",
                agent_id="1000002",
                app_secret="secret-1",
                callback_url="https://bi.example.com/api/auth/wechat-work/callback",
                robot_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
            ),
            db=db,
            current_user=self._admin(),
        )

        self.assertTrue(response.enabled)
        self.assertTrue(response.app_secret_set)
        self.assertFalse(hasattr(response, "app_secret"))
        self.assertEqual(db.query(IntegrationConfig).one().app_secret, "secret-1")

        update_wechat_work_config(
            WechatWorkConfigUpdate(enabled=False, app_secret=None),
            db=db,
            current_user=self._admin(),
        )
        self.assertEqual(db.query(IntegrationConfig).one().app_secret, "secret-1")

        read_response = get_wechat_work_config(db=db, current_user=self._admin())
        self.assertFalse(read_response.enabled)
        self.assertTrue(read_response.app_secret_set)

    def test_org_bindings_can_be_created_listed_and_deleted(self):
        from app.api.integrations import (
            create_wechat_work_org_binding,
            delete_wechat_work_org_binding,
            list_wechat_work_org_bindings,
        )
        from app.schemas.integration import ExternalOrgBindingCreate

        db = self._db()
        created = create_wechat_work_org_binding(
            ExternalOrgBindingCreate(external_corp_id="corp-1", org_id=2),
            db=db,
            current_user=self._admin(),
        )
        self.assertEqual(created.external_corp_id, "corp-1")
        self.assertEqual(created.org_name, "嘉盛半导体")

        listed = list_wechat_work_org_bindings(db=db, current_user=self._admin())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, created.id)

        delete_wechat_work_org_binding(created.id, db=db, current_user=self._admin())
        self.assertEqual(list_wechat_work_org_bindings(db=db, current_user=self._admin()), [])

    def test_permission_mappings_reject_super_admin_role(self):
        from app.api.integrations import (
            create_wechat_work_permission_mapping,
            update_wechat_work_permission_mapping,
        )
        from app.schemas.integration import ExternalPermissionMappingCreate, ExternalPermissionMappingUpdate

        db = self._db()
        with self.assertRaises(HTTPException) as create_ctx:
            create_wechat_work_permission_mapping(
                ExternalPermissionMappingCreate(
                    external_corp_id="corp-1",
                    external_department_id="7",
                    org_id=2,
                    role="super_admin",
                ),
                db=db,
                current_user=self._admin(),
            )
        self.assertEqual(create_ctx.exception.status_code, 400)

        mapping = create_wechat_work_permission_mapping(
            ExternalPermissionMappingCreate(
                external_corp_id="corp-1",
                external_department_id="7",
                org_id=2,
                role="org_admin",
                data_scope="org",
                menu_permissions={"dashboard.view": True},
                action_permissions={"dashboard.read": True},
            ),
            db=db,
            current_user=self._admin(),
        )
        self.assertEqual(mapping.role, "org_admin")
        self.assertEqual(mapping.menu_permissions, {"dashboard.view": True})

        with self.assertRaises(HTTPException) as update_ctx:
            update_wechat_work_permission_mapping(
                mapping.id,
                ExternalPermissionMappingUpdate(role="super_admin"),
                db=db,
                current_user=self._admin(),
            )
        self.assertEqual(update_ctx.exception.status_code, 400)

    def test_message_test_endpoint_creates_delivery(self):
        from app.api.integrations import send_wechat_work_test_message
        from app.schemas.integration import WechatWorkMessageTestRequest

        db = self._db()
        deliveries = send_wechat_work_test_message(
            WechatWorkMessageTestRequest(
                recipient_user_id=8,
                title="Smart BI 企业微信测试",
                content="这是一条测试消息",
            ),
            db=db,
            current_user=self._admin(),
        )

        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0].recipient_user_id, 8)
        self.assertEqual(deliveries[0].event_type, "approval.requested")
        self.assertEqual(deliveries[0].status, "failed")
