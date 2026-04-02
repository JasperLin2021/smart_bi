import json
import io
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path


class AgentSkillsTests(unittest.TestCase):
    def test_scan_local_skills(self):
        from app.core.agent_skills import scan_skill_dirs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "demo-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: demo-skill
                    description: Demo skill for testing
                    ---

                    # Demo
                    """
                ),
                encoding="utf-8",
            )

            items = scan_skill_dirs([root])
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["name"], "demo-skill")
            self.assertEqual(items[0]["description"], "Demo skill for testing")
            self.assertEqual(items[0]["source"], "local")

    def test_scan_skill_uses_registry_source(self):
        from app.core.agent_skills import scan_skill_dirs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "demo-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (skill_dir / ".agent-skill.json").write_text(
                json.dumps({"source": "github:openai/skills@main"}),
                encoding="utf-8",
            )

            items = scan_skill_dirs([root])
            self.assertEqual(items[0]["source"], "github:openai/skills@main")

    def test_parse_github_tree_url(self):
        from app.core.agent_skills import parse_github_skill_source

        parsed = parse_github_skill_source(
            "https://github.com/openai/skills/tree/main/skills/.curated/example-skill"
        )
        self.assertEqual(parsed["repo"], "openai/skills")
        self.assertEqual(parsed["ref"], "main")
        self.assertEqual(parsed["path"], "skills/.curated/example-skill")

    def test_parse_github_repo_path(self):
        from app.core.agent_skills import parse_github_skill_source

        parsed = parse_github_skill_source("openai/skills:skills/.curated/example-skill")
        self.assertEqual(parsed["repo"], "openai/skills")
        self.assertEqual(parsed["ref"], "main")
        self.assertEqual(parsed["path"], "skills/.curated/example-skill")

    def test_parse_github_repo_path_with_ref(self):
        from app.core.agent_skills import parse_github_skill_source

        parsed = parse_github_skill_source("openai/skills@develop:skills/.curated/example-skill")
        self.assertEqual(parsed["repo"], "openai/skills")
        self.assertEqual(parsed["ref"], "develop")
        self.assertEqual(parsed["path"], "skills/.curated/example-skill")

    def test_extract_skill_from_zipball(self):
        from app.core.agent_skills import extract_skill_from_zipball

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("repo-main/skills/skill-creator/SKILL.md", "# Skill Creator\n")
            zf.writestr("repo-main/skills/skill-creator/references/readme.md", "ref")
            zf.writestr("repo-main/README.md", "root")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skill-creator"
            extract_skill_from_zipball(archive.getvalue(), "skills/skill-creator", target)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertEqual((target / "references" / "readme.md").read_text(encoding="utf-8"), "ref")


if __name__ == "__main__":
    unittest.main()
