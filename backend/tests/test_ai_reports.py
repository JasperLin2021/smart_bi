"""对话式 AI 报表（ai-reports）与内部 LLM 配置端点的单元测试。

覆盖：
- CRUD 与 org 隔离（跨 org 404、super_admin 可见全部）
- 删除权限（owner / org_admin / super_admin）
- share / unshare / 公开访问（无需鉴权）
- publish-to-report-center 生成 ai_html 模板且 dataset_id 为 NULL
- GET /api/internal/llm-config：未配置 secret 403、密钥错误 401、密钥正确 200
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.ai_report import AiReport
from app.models.report_template import ReportTemplate


def _db():
    from app.db.base import Base  # noqa: F401 - 触发所有模型注册到 metadata

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(user_id=1, role="user", org_id=1):
    return SimpleNamespace(id=user_id, role=role, org_id=org_id, username=f"user{user_id}")


def _create_report(db, user, title="销售分析", html="<h1>report</h1>"):
    from app.api.ai_reports import create_ai_report
    from app.schemas.ai_report import AiReportCreate

    return create_ai_report(
        AiReportCreate(title=title, html=html, conversation_json='[{"role":"user"}]'),
        db=db,
        current_user=user,
    )


class AiReportCrudTests(unittest.TestCase):
    def test_create_and_get_roundtrip(self):
        from app.api.ai_reports import get_ai_report

        db = _db()
        user = _user()
        report = _create_report(db, user)
        self.assertEqual(report.status, "draft")
        self.assertEqual(report.org_id, 1)
        self.assertEqual(report.owner_id, 1)
        self.assertIsNone(report.share_token)

        fetched = get_ai_report(report.id, db=db, current_user=user)
        self.assertEqual(fetched.html, "<h1>report</h1>")
        self.assertEqual(fetched.conversation_json, '[{"role":"user"}]')

    def test_create_rejects_blank_title(self):
        from app.api.ai_reports import create_ai_report
        from app.schemas.ai_report import AiReportCreate

        db = _db()
        with self.assertRaises(HTTPException) as ctx:
            create_ai_report(
                AiReportCreate(title="   ", html="<p>x</p>"),
                db=db,
                current_user=_user(),
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_rejects_oversized_html(self):
        from app.schemas.ai_report import AI_REPORT_HTML_MAX_BYTES, AiReportCreate

        with self.assertRaises(ValidationError):
            AiReportCreate(title="t", html="x" * (AI_REPORT_HTML_MAX_BYTES + 1))

    def test_list_excludes_html_field(self):
        from app.api.ai_reports import list_ai_reports
        from app.schemas.ai_report import AiReportListItem

        self.assertNotIn("html", AiReportListItem.model_fields)
        self.assertNotIn("conversation_json", AiReportListItem.model_fields)

        db = _db()
        user = _user()
        _create_report(db, user)
        _create_report(db, user, title="库存分析")
        result = list_ai_reports(db=db, current_user=user)
        self.assertEqual(result["total"], 2)

    def test_org_isolation(self):
        from app.api.ai_reports import get_ai_report, list_ai_reports

        db = _db()
        report = _create_report(db, _user(org_id=1))

        outsider = _user(user_id=2, org_id=2)
        with self.assertRaises(HTTPException) as ctx:
            get_ai_report(report.id, db=db, current_user=outsider)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(list_ai_reports(db=db, current_user=outsider)["total"], 0)

        org_admin_outside = _user(user_id=3, role="org_admin", org_id=2)
        with self.assertRaises(HTTPException) as ctx:
            get_ai_report(report.id, db=db, current_user=org_admin_outside)
        self.assertEqual(ctx.exception.status_code, 404)

        super_admin = _user(user_id=4, role="super_admin", org_id=None)
        fetched = get_ai_report(report.id, db=db, current_user=super_admin)
        self.assertEqual(fetched.id, report.id)
        self.assertEqual(list_ai_reports(db=db, current_user=super_admin)["total"], 1)

    def test_delete_permissions(self):
        from app.api.ai_reports import delete_ai_report

        db = _db()
        report = _create_report(db, _user())

        colleague = _user(user_id=2, org_id=1)
        with self.assertRaises(HTTPException) as ctx:
            delete_ai_report(report.id, db=db, current_user=colleague)
        self.assertEqual(ctx.exception.status_code, 403)

        org_admin = _user(user_id=3, role="org_admin", org_id=1)
        result = delete_ai_report(report.id, db=db, current_user=org_admin)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(db.query(AiReport).filter(AiReport.id == report.id).first())

    def test_owner_can_delete_own_report(self):
        from app.api.ai_reports import delete_ai_report

        db = _db()
        user = _user()
        report = _create_report(db, user)
        result = delete_ai_report(report.id, db=db, current_user=user)
        self.assertEqual(result["status"], "ok")


class AiReportShareTests(unittest.TestCase):
    def test_share_unshare_public_access(self):
        from app.api.ai_reports import get_shared_ai_report, share_ai_report, unshare_ai_report

        db = _db()
        user = _user()
        report = _create_report(db, user)

        token = share_ai_report(report.id, db=db, current_user=user)["share_token"]
        self.assertTrue(token)

        shared = get_shared_ai_report(token, db=db)
        self.assertEqual(shared.title, "销售分析")
        self.assertEqual(shared.html, "<h1>report</h1>")

        unshare_ai_report(report.id, db=db, current_user=user)
        with self.assertRaises(HTTPException) as ctx:
            get_shared_ai_report(token, db=db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_share_requires_manage_permission(self):
        from app.api.ai_reports import share_ai_report

        db = _db()
        report = _create_report(db, _user())
        colleague = _user(user_id=2, org_id=1)
        with self.assertRaises(HTTPException) as ctx:
            share_ai_report(report.id, db=db, current_user=colleague)
        self.assertEqual(ctx.exception.status_code, 403)


class AiReportPublishTests(unittest.TestCase):
    def test_publish_creates_ai_html_template_without_dataset(self):
        from app.api.ai_reports import publish_ai_report_to_report_center
        from app.api.report_templates import VALID_REPORT_TYPES, _ensure_values

        self.assertIn("ai_html", VALID_REPORT_TYPES)
        _ensure_values(report_type="ai_html")  # 不抛异常

        db = _db()
        user = _user()
        report = _create_report(db, user)

        result = publish_ai_report_to_report_center(report.id, db=db, current_user=user)
        template = db.query(ReportTemplate).filter(ReportTemplate.id == result["template_id"]).one()
        self.assertEqual(template.report_type, "ai_html")
        self.assertIsNone(template.dataset_id)
        self.assertEqual(template.status, "published")
        self.assertEqual(template.name, "销售分析")
        self.assertEqual(template.layout_json, {"kind": "html", "html": "<h1>report</h1>"})
        self.assertEqual(template.org_id, 1)
        self.assertEqual(template.owner_id, user.id)

    def test_publish_respects_org_isolation(self):
        from app.api.ai_reports import publish_ai_report_to_report_center

        db = _db()
        report = _create_report(db, _user(org_id=1))
        outsider = _user(user_id=2, org_id=2)
        with self.assertRaises(HTTPException) as ctx:
            publish_ai_report_to_report_center(report.id, db=db, current_user=outsider)
        self.assertEqual(ctx.exception.status_code, 404)


class InternalLlmConfigTests(unittest.TestCase):
    def test_rejects_when_secret_not_configured(self):
        from app.api.internal import get_internal_llm_config
        from app.core.config import settings

        with patch.object(settings, "internal_api_secret", ""):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(get_internal_llm_config(x_internal_secret="anything"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_rejects_wrong_secret(self):
        from app.api.internal import get_internal_llm_config
        from app.core.config import settings

        with patch.object(settings, "internal_api_secret", "s3cr3t"):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(get_internal_llm_config(x_internal_secret="wrong"))
            self.assertEqual(ctx.exception.status_code, 401)
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(get_internal_llm_config(x_internal_secret=None))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_returns_llm_config_with_valid_secret(self):
        from app.api.internal import get_internal_llm_config
        from app.core.config import settings

        fake_config = {
            "provider": "custom",
            "base_url": "https://example.com/v1",
            "api_key": "plain-text-key",
            "model": "demo-model",
            "temperature": 0.3,
        }
        with patch.object(settings, "internal_api_secret", "s3cr3t"):
            with patch("app.api.internal.get_llm_config", new=AsyncMock(return_value=fake_config)):
                result = asyncio.run(get_internal_llm_config(x_internal_secret="s3cr3t"))
        self.assertEqual(result["api_key"], "plain-text-key")
        self.assertEqual(result["model"], "demo-model")


if __name__ == "__main__":
    unittest.main()
