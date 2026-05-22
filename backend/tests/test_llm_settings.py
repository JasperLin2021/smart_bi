import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException


class LlmSettingsTests(unittest.TestCase):
    def test_test_llm_connection_uses_override_config(self):
        from app.core.llm import test_llm_connection

        override = {
            "provider": "custom",
            "base_url": "https://example.com/v1",
            "api_key": "demo-key",
            "model": "demo-model",
            "temperature": 0.4,
        }

        with patch("app.core.llm.chat_completion", new=AsyncMock(return_value="pong")) as mocked:
            result = asyncio.run(test_llm_connection(override))

        self.assertEqual(result["status"], "ok")
        self.assertIn("连接成功", result["message"])
        mocked.assert_awaited_once()
        _, kwargs = mocked.await_args
        self.assertEqual(kwargs["config_override"]["model"], "demo-model")
        self.assertEqual(kwargs["temperature"], 0)

    def test_test_llm_connection_preserves_gemini_preview_model(self):
        from app.core.llm import test_llm_connection

        override = {
            "provider": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "demo-key",
            "model": "gemini-3.1-flash-lite-preview",
            "temperature": 0.4,
        }

        with patch("app.core.llm.chat_completion", new=AsyncMock(return_value="pong")) as mocked:
            result = asyncio.run(test_llm_connection(override))

        self.assertEqual(result["status"], "ok")
        _, kwargs = mocked.await_args
        self.assertEqual(kwargs["config_override"]["model"], "gemini-3.1-flash-lite-preview")
        self.assertEqual(kwargs["temperature"], 0)

    def test_dashscope_normalization_defaults_to_bailian_qwen36(self):
        from app.core.llm import normalize_llm_config

        config = normalize_llm_config(
            {
                "provider": "aliyun_bailian",
                "base_url": "",
                "api_key": "demo-key",
                "model": "",
                "temperature": 0.3,
            }
        )

        self.assertEqual(config["provider"], "dashscope")
        self.assertEqual(config["base_url"], "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(config["model"], "qwen3.6-35b-a3b")

    def test_pi_mono_normalization_defaults_to_openai_compatible_endpoint(self):
        from app.core.llm import normalize_llm_config

        config = normalize_llm_config(
            {
                "provider": "pi_mono",
                "base_url": "",
                "api_key": "",
                "model": "",
                "temperature": 0.2,
            }
        )

        self.assertEqual(config["provider"], "pi")
        self.assertEqual(config["base_url"], "http://localhost:8001/v1")
        self.assertEqual(config["model"], "pi/pi-mono")

    def test_gemma4_normalization_uses_gemini_api_with_gemma4_model(self):
        from app.core.llm import normalize_llm_config

        config = normalize_llm_config(
            {
                "provider": "gemma4",
                "base_url": "",
                "api_key": "demo-key",
                "model": "",
                "temperature": 0.3,
            }
        )

        self.assertEqual(config["provider"], "gemini")
        self.assertEqual(config["base_url"], "https://generativelanguage.googleapis.com/v1beta")
        self.assertEqual(config["model"], "gemma-4-31b-it")

    def test_llm_http_timeout_allows_slow_gemma_generation(self):
        from app.core.llm import _llm_http_timeout, normalize_llm_config

        config = normalize_llm_config(
            {
                "provider": "gemma4",
                "base_url": "",
                "api_key": "demo-key",
                "model": "",
                "temperature": 0.3,
            }
        )

        timeout = _llm_http_timeout(config)

        self.assertGreaterEqual(timeout.read, 120)
        self.assertLessEqual(timeout.connect, 15)

    def test_update_llm_setting_preserves_saved_gemini_model_name(self):
        from app.api.settings import update_llm_setting
        from app.schemas.settings import LlmConfigUpdate

        record = SimpleNamespace(
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key="demo-key",
            model="gemini-2.5-flash-lite",
            temperature=0.3,
            agent_planner_mode="llm_only",
        )

        class FakeQuery:
            def __init__(self, row):
                self.row = row

            def first(self):
                return self.row

        class FakeDb:
            def __init__(self, row):
                self.row = row

            def query(self, _model):
                return FakeQuery(self.row)

            def add(self, row):
                self.row = row

            def commit(self):
                return None

            def refresh(self, _row):
                return None

        payload = LlmConfigUpdate(
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-3.1-flash-lite-preview",
            temperature=0.3,
            agent_planner_mode="llm_only",
            api_key="",
        )

        with patch("app.api.settings.set_llm_config_cache") as mocked_cache:
            result = update_llm_setting(
                payload,
                db=FakeDb(record),
                current_user=SimpleNamespace(role="super_admin"),
            )

        self.assertEqual(record.model, "gemini-3.1-flash-lite-preview")
        self.assertEqual(result["model"], "gemini-3.1-flash-lite-preview")
        cached = mocked_cache.call_args.args[0]
        self.assertEqual(cached["model"], "gemini-3.1-flash-lite-preview")

    def test_test_llm_setting_translates_provider_errors(self):
        from app.api.settings import test_llm_setting
        from app.schemas.settings import LlmConfigTestRequest

        payload = LlmConfigTestRequest(
            provider="custom",
            base_url="https://example.com/v1",
            model="demo-model",
            temperature=0.3,
            api_key="demo-key",
        )
        user = SimpleNamespace(role="super_admin")
        db = SimpleNamespace()
        db.query = lambda *_args, **_kwargs: SimpleNamespace(
            first=lambda: SimpleNamespace(api_key="saved-key")
        )

        request = httpx.Request("POST", "https://example.com/v1/chat/completions")
        response = httpx.Response(401, request=request, text='{"error":"bad api key"}')
        error = httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)

        with patch("app.api.settings.test_llm_connection", new=AsyncMock(side_effect=error)):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(test_llm_setting(payload, db=db, current_user=user))

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("LLM 连接测试失败", ctx.exception.detail)
        self.assertIn("bad api key", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
