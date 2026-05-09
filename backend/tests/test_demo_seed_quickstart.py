import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose_text: str, service_name: str) -> str:
    match = re.search(
        rf"^  {re.escape(service_name)}:\n(?P<body>(?:    .*\n|      .*\n|        .*\n|          .*\n|            .*\n|              .*\n|                .*\n|                  .*\n)*)",
        compose_text,
        flags=re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"{service_name} service not found")
    return match.group("body")


class DemoSeedQuickstartTests(unittest.TestCase):
    def test_default_compose_imports_mock_data_without_profile(self):
        compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        demo_seed = _service_block(compose_text, "demo-seed")

        self.assertNotIn("profiles:", demo_seed)
        self.assertIn("./mock_data.sql:/mock_data.sql:ro", demo_seed)
        self.assertIn("psql -v ON_ERROR_STOP=1 -f /mock_data.sql", demo_seed)
        self.assertIn("backend:", demo_seed)
        self.assertIn("condition: service_healthy", demo_seed)

    def test_readme_quickstart_mentions_automatic_demo_seed(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("docker compose up -d --build", readme)
        self.assertIn("mock_data.sql", readme)
        self.assertIn("自动导入", readme)
        self.assertIn("automatically imports", readme)


if __name__ == "__main__":
    unittest.main()
