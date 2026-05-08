import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class WechatWorkMappingModelTests(unittest.TestCase):
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
        return sessionmaker(bind=engine)()

    def test_wechat_work_integration_models_persist_bindings_mappings_and_deliveries(self):
        from app.models.integration import (
            ExternalIdentity,
            ExternalOrgBinding,
            ExternalPermissionMapping,
            IntegrationConfig,
            MessageDelivery,
        )
        from app.models.organization import Organization
        from app.models.user import User

        db = self._db()
        org = Organization(id=2, name="嘉盛半导体", slug="carsem")
        user = User(
            username="ww:corp-1:zhangsan",
            hashed_password="!",
            role="user",
            org_id=2,
        )
        db.add_all([org, user])
        db.flush()

        config = IntegrationConfig(
            provider="wechat_work",
            name="企业微信",
            enabled=True,
            corp_id="corp-1",
            agent_id="1000002",
            app_secret="secret",
            callback_url="https://bi.example.com/api/auth/wechat-work/callback",
            robot_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
        )
        binding = ExternalOrgBinding(
            provider="wechat_work",
            external_corp_id="corp-1",
            org_id=org.id,
        )
        identity = ExternalIdentity(
            provider="wechat_work",
            external_corp_id="corp-1",
            external_user_id="zhangsan",
            user_id=user.id,
            display_name="张三",
            department_ids_json='["7"]',
        )
        mapping = ExternalPermissionMapping(
            provider="wechat_work",
            external_corp_id="corp-1",
            external_department_id="7",
            org_id=org.id,
            role="org_admin",
            data_scope="org",
            priority=10,
        )
        delivery = MessageDelivery(
            provider="wechat_work",
            channel="wechat_app",
            event_type="action_item.assigned",
            recipient_user_id=user.id,
            recipient_external_user_id="zhangsan",
            org_id=org.id,
            title="行动项提醒",
            content="请处理异常工单",
            link_url="/action-items",
        )
        db.add_all([config, binding, identity, mapping, delivery])
        db.commit()

        saved_identity = db.query(ExternalIdentity).one()
        self.assertEqual(saved_identity.external_corp_id, "corp-1")
        self.assertEqual(saved_identity.external_user_id, "zhangsan")
        self.assertEqual(saved_identity.user_id, user.id)

        saved_mapping = db.query(ExternalPermissionMapping).one()
        self.assertEqual(saved_mapping.role, "org_admin")
        self.assertEqual(saved_mapping.priority, 10)

        saved_delivery = db.query(MessageDelivery).one()
        self.assertEqual(saved_delivery.status, "pending")
        self.assertEqual(saved_delivery.channel, "wechat_app")

        identity_constraints = {
            constraint.name for constraint in ExternalIdentity.__table__.constraints
        }
        org_constraints = {
            constraint.name for constraint in ExternalOrgBinding.__table__.constraints
        }
        self.assertIn("uq_external_identity", identity_constraints)
        self.assertIn("uq_external_org_provider_corp", org_constraints)
