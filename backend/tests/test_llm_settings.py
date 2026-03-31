import asyncio
import unittest
from unittest.mock import AsyncMock, patch


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


if __name__ == "__main__":
    unittest.main()
