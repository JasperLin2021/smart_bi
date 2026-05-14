import json
import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

import httpx


PROJECT_SKILLS_DIR = Path("/home/qqr/smart_bi/.agent-skills")
USER_SKILLS_DIR = Path.home() / ".codex" / "skills"


BUILTIN_SKILLS = [
    {
        "name": "navigation",
        "description": "Use for page navigation across the current workspace, data preparation, BI analysis and system admin menus.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "switch_datasource"],
    },
    {
        "name": "query_analysis",
        "description": "Use for smart-query and drill analysis tasks.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "switch_datasource", "ask_query"],
    },
    {
        "name": "datasource_admin",
        "description": "Use for connector and datasource creation, testing, schema detection and drill config generation.",
        "source": "builtin",
        "path": None,
        "allowed_actions": [
            "navigate",
            "create_datasource",
            "update_datasource",
            "delete_datasource",
            "test_datasource",
            "detect_schema",
            "generate_drill_config",
        ],
    },
    {
        "name": "dataset_admin",
        "description": "Use for dataset development, semantic modeling, publishing and refresh workflows.",
        "source": "builtin",
        "path": None,
        "allowed_actions": [
            "navigate",
            "create_dataset",
            "update_dataset",
            "publish_dataset",
            "refresh_dataset",
            "delete_dataset",
        ],
    },
    {
        "name": "dashboard_admin",
        "description": "Use for dashboard center creation, update, publishing and deletion workflows.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_dashboard", "update_dashboard", "publish_dashboard", "delete_dashboard"],
    },
    {
        "name": "analysis_workbench",
        "description": "Use for self-service analysis views, reusable analysis and publishing to BI assets.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_analysis_view", "update_analysis_view", "publish_analysis_view"],
    },
    {
        "name": "pipeline_admin",
        "description": "Use for data processing pipelines, scheduling, backfill and operational runs.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_pipeline", "run_pipeline", "delete_pipeline"],
    },
    {
        "name": "report_admin",
        "description": "Use for complex report templates, paginated reports and fill-form report maintenance.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_report_template", "update_report_template", "delete_report_template"],
    },
    {
        "name": "action_item",
        "description": "Use for creating and maintaining action items from analysis, alerts, dashboards or manual follow-ups.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_action_item", "update_action_item", "delete_action_item"],
    },
    {
        "name": "user_admin",
        "description": "Use for user creation and user management workflows.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_user", "update_user", "delete_user"],
    },
    {
        "name": "organization_admin",
        "description": "Use for organization creation and maintenance.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_organization", "update_organization", "delete_organization"],
    },
    {
        "name": "metric_admin",
        "description": "Use for metric configuration maintenance.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "create_metric", "update_metric", "delete_metric"],
    },
    {
        "name": "llm_admin",
        "description": "Use for large-model configuration maintenance.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["navigate", "update_llm_settings", "refresh_llm_settings"],
    },
    {
        "name": "skill_admin",
        "description": "Use for listing and installing external Agent skills from compatible SKILL.md packages.",
        "source": "builtin",
        "path": None,
        "allowed_actions": ["install_agent_skill"],
    },
]


def _parse_frontmatter(skill_file: Path) -> dict:
    content = skill_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}
    match = re.match(r"^---\n(.*?)\n---\n", content, re.S)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def scan_skill_dirs(skill_roots: List[Path]) -> List[dict]:
    items: List[dict] = []
    for root in skill_roots:
        if not root.exists():
            continue
        for skill_file in root.glob("*/SKILL.md"):
            meta = _parse_frontmatter(skill_file)
            registry_meta = {}
            registry_file = skill_file.parent / ".agent-skill.json"
            if registry_file.exists():
                try:
                    registry_meta = json.loads(registry_file.read_text(encoding="utf-8"))
                except Exception:
                    registry_meta = {}
            items.append(
                {
                    "name": meta.get("name") or skill_file.parent.name,
                    "description": meta.get("description") or "",
                    "source": registry_meta.get("source") or "local",
                    "path": str(skill_file.parent),
                    "allowed_actions": [],
                }
            )
    return items


def list_agent_skills() -> List[dict]:
    return BUILTIN_SKILLS + scan_skill_dirs([PROJECT_SKILLS_DIR, USER_SKILLS_DIR])


def parse_github_skill_source(source: str) -> Dict[str, str]:
    if source.startswith("http://") or source.startswith("https://"):
        parsed = urlparse(source)
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 5 or parts[2] != "tree":
            raise ValueError("GitHub URL 必须是 tree 路径")
        return {
            "repo": f"{parts[0]}/{parts[1]}",
            "ref": parts[3],
            "path": "/".join(parts[4:]),
        }

    if ":" not in source:
        raise ValueError("GitHub skill source 格式必须是 owner/repo:path/to/skill")
    repo_ref, path = source.split(":", 1)
    ref = "main"
    repo = repo_ref
    if "@" in repo_ref:
        repo, ref = repo_ref.rsplit("@", 1)
    return {"repo": repo, "ref": ref, "path": path}


async def install_skill_from_github(source: str) -> dict:
    parsed = parse_github_skill_source(source)
    repo = parsed["repo"]
    ref = parsed["ref"]
    path = parsed["path"].strip("/")
    skill_name = Path(path).name
    target_dir = PROJECT_SKILLS_DIR / skill_name
    if target_dir.exists():
        raise ValueError(f"Skill {skill_name} 已安装")

    PROJECT_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            archive_url = f"https://api.github.com/repos/{repo}/zipball/{ref}"
            response = await client.get(archive_url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()

            target_dir.mkdir()
            extract_skill_from_zipball(response.content, path, target_dir)
            if not (target_dir / "SKILL.md").exists():
                raise ValueError("Skill 目录缺少 SKILL.md")
            (target_dir / ".agent-skill.json").write_text(
                json.dumps({"source": f"github:{repo}@{ref}"}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except httpx.HTTPStatusError as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            if exc.response.status_code == 403:
                raise ValueError("GitHub API 限流或拒绝访问，稍后重试或改用本地导入") from exc
            if exc.response.status_code == 404:
                raise ValueError("GitHub skill 路径不存在，请检查仓库、分支和目录") from exc
            raise ValueError(f"GitHub 下载失败：HTTP {exc.response.status_code}") from exc
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

    meta = _parse_frontmatter(target_dir / "SKILL.md")
    return {
        "name": meta.get("name") or skill_name,
        "description": meta.get("description") or "",
        "source": f"github:{repo}@{ref}",
        "path": str(target_dir),
        "allowed_actions": [],
    }


def extract_skill_from_zipball(archive_bytes: bytes, remote_path: str, target_dir: Path):
    normalized_target = remote_path.strip("/")
    matched = False

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            filename = member.filename.strip("/")
            if not filename:
                continue

            parts = filename.split("/", 1)
            if len(parts) != 2:
                continue

            inner_path = parts[1]
            if inner_path == normalized_target:
                matched = True
                continue
            if not inner_path.startswith(f"{normalized_target}/"):
                continue

            matched = True
            relative_path = inner_path[len(normalized_target) + 1 :]
            if not relative_path:
                continue

            destination = target_dir / Path(relative_path)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                output.write(source.read())

    if not matched:
        raise ValueError("给定路径不是 skill 目录")
