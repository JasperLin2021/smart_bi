import json
import re
from typing import Any, Dict, List

from app.core.agent_actions import ACTION_SPECS, get_action_catalog
from app.core.agent_skills import list_agent_skills
from app.core.llm import chat_completion


ROUTE_MAP = {
    "dashboard": "/dashboard",
    "仪表盘": "/dashboard",
    "工作台": "/dashboard",
    "智能问数": "/smart-query",
    "问数": "/smart-query",
    "自助分析": "/analysis-workbench",
    "行动闭环": "/action-items",
    "大屏中心": "/big-screen-center",
    "看板中心": "/dashboard-center",
    "复杂报表": "/report-center",
    "数据准备": "/data-development",
    "准备总览": "/data-development",
    "连接器接入": "/data-link",
    "数据接入": "/data-development",
    "数据源": "/data-development?tab=datasources",
    "数据源管理": "/data-development?tab=datasources",
    "数据集": "/data-development?tab=datasets",
    "数据集开发": "/data-development?tab=datasets",
    "数据源与数据集": "/data-development",
    "可视化ETL": "/data-pipelines",
    "数据加工管道": "/data-pipelines",
    "数据集成管道": "/data-pipelines",
    "数据平台": "/olap-status",
    "OLAP 数据平台": "/olap-status",
    "Doris": "/olap-status",
    "用户管理": "/access-control",
    "企业管理": "/access-control",
    "权限管理": "/access-control",
    "指标配置": "/metric-settings",
    "可信指标": "/metric-settings",
    "预警管理": "/alert-settings",
    "定时报告": "/scheduled-reports",
    "数据目录": "/data-catalog",
    "运营后台": "/operations",
    "审计日志": "/audit-logs",
    "大模型配置": "/llm-settings",
    "通知配置": "/notification-settings",
    "企业微信集成": "/wechat-work-integration",
}

ROUTE_PERMISSIONS = {
    "/dashboard": ["user", "dept_admin", "org_admin", "super_admin"],
    "/smart-query": ["user", "dept_admin", "org_admin", "super_admin"],
    "/analysis-workbench": ["user", "dept_admin", "org_admin", "super_admin"],
    "/action-items": ["user", "dept_admin", "org_admin", "super_admin"],
    "/big-screen-center": ["user", "dept_admin", "org_admin", "super_admin"],
    "/dashboard-center": ["user", "dept_admin", "org_admin", "super_admin"],
    "/report-center": ["user", "dept_admin", "org_admin", "super_admin"],
    "/data-access": ["user", "dept_admin", "org_admin", "super_admin"],
    "/data-link": ["org_admin", "super_admin"],
    "/data-development": ["user", "dept_admin", "org_admin", "super_admin"],
    "/data-pipelines": ["dept_admin", "org_admin", "super_admin"],
    "/olap-status": ["org_admin", "super_admin"],
    "/data-catalog": ["user", "dept_admin", "org_admin", "super_admin"],
    "/metric-settings": ["user", "dept_admin", "org_admin", "super_admin"],
    "/alert-settings": ["user", "dept_admin", "org_admin", "super_admin"],
    "/scheduled-reports": ["user", "dept_admin", "org_admin", "super_admin"],
    "/access-control": ["org_admin", "super_admin"],
    "/audit-logs": ["org_admin", "super_admin"],
    "/operations": ["org_admin", "super_admin"],
    "/llm-settings": ["super_admin"],
    "/notification-settings": ["super_admin"],
    "/wechat-work-integration": ["super_admin"],
}

LEGACY_ROUTE_ALIASES = {
    "/datasource-settings": "/data-development?tab=datasources",
    "/dataset-center": "/data-development?tab=datasets",
    "/user-management": "/access-control",
    "/role-management": "/access-control",
    "/org-management": "/access-control",
    "/goview": "/big-screen-center",
}


def normalize_route(route: Any) -> str:
    value = str(route or "").strip()
    if not value:
        return ""
    return LEGACY_ROUTE_ALIASES.get(value, value)


def route_path(route: str) -> str:
    return normalize_route(route).split("?", 1)[0]


def route_allowed(route: str, allowed_routes: List[str]) -> bool:
    normalized = normalize_route(route)
    allowed_variants: set[str] = set()
    for allowed_route in allowed_routes:
        normalized_allowed = normalize_route(allowed_route)
        allowed_variants.add(normalized_allowed)
        allowed_variants.add(route_path(normalized_allowed))
    return normalized in allowed_variants or route_path(normalized) in allowed_variants


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        match = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if match:
            text = match[0].strip()
    return json.loads(text)


def _risk_for_actions(actions: List[dict]) -> str:
    if not actions:
        return "low"
    if any(item["risk"] == "high" for item in actions):
        return "high"
    if any(item["risk"] == "medium" for item in actions):
        return "medium"
    return "low"


def apply_skill_action_constraints(actions: List[dict], skill: dict | None) -> List[dict]:
    if not skill or not skill.get("allowed_actions"):
        return actions
    allowed = set(skill["allowed_actions"])
    return [item for item in actions if item["type"] in allowed]


def select_skill(message: str, context: dict) -> dict | None:
    lowered = message.lower()
    skills = context.get("skills") or []

    def find(name: str):
        return next((item for item in skills if item["name"] == name), None)

    if any(word in message for word in ["安装", "skill", "技能"]) and "http" in lowered:
        return find("skill_admin")

    for skill in skills:
        skill_name = str(skill.get("name") or "").lower()
        if skill_name and (skill_name in lowered or f"${skill_name}" in lowered):
            return skill

    if any(word in message for word in ["打开", "进入", "跳转", "切到"]) and not any(
        word in message for word in ["创建", "新增", "删除", "修改", "更新", "测试", "检测", "生成"]
    ):
        return find("navigation")
    if any(word in message for word in ["数据集", "dataset"]):
        return find("dataset_admin")
    if any(word in message for word in ["数据源", "schema", "表结构", "钻取规则"]):
        return find("datasource_admin")
    if any(word in message for word in ["看板", "dashboard"]):
        return find("dashboard_admin")
    if any(word in message for word in ["管道", "ETL", "补数", "调度"]):
        return find("pipeline_admin")
    if any(word in message for word in ["复杂报表", "报表模板", "分页报表", "填报"]):
        return find("report_admin")
    if any(word in message for word in ["行动项", "行动闭环", "闭环"]):
        return find("action_item")
    if any(word in message for word in ["自助分析", "分析视图"]):
        return find("analysis_workbench")
    if any(word in message for word in ["用户", "账号", "密码", "角色"]):
        return find("user_admin")
    if any(word in message for word in ["企业管理", "企业", "组织"]):
        return find("organization_admin")
    if any(word in message for word in ["指标", "metric"]):
        return find("metric_admin")
    if any(word in message for word in ["模型配置", "llm", "openai", "deepseek", "gemini"]):
        return find("llm_admin")
    if any(word in message for word in ["查询", "统计", "分析", "问数", "趋势", "top"]):
        return find("query_analysis")
    return None


def should_use_heuristics(context: dict) -> bool:
    return context.get("agent_planner_mode") == "heuristic_then_llm"


def _heuristic_plan(message: str, context: dict) -> dict | None:
    stripped = message.strip()
    for keyword, route in ROUTE_MAP.items():
        if (
            keyword in stripped
            and any(item["type"] == "navigate" for item in context["allowed_actions"])
            and route_allowed(route, context["allowed_routes"])
        ):
            return {
                "reply": f"准备跳转到{keyword}页面。",
                "reasoning": "命中了明确页面导航意图。",
                "actions": [
                    {
                        "type": "navigate",
                        "label": f"打开{keyword}",
                        "risk": ACTION_SPECS["navigate"]["risk"],
                        "params": {"route": normalize_route(route)},
                    }
                ],
            }

    if any(word in stripped for word in ["切换数据源", "切到数据源", "使用数据源"]) and context.get("datasource_names"):
        for name in context["datasource_names"]:
            if name in stripped:
                return {
                    "reply": f"准备切换到数据源 {name}。",
                    "reasoning": "命中了数据源切换意图。",
                    "actions": [
                        {
                            "type": "switch_datasource",
                            "label": f"切换到{name}",
                            "risk": ACTION_SPECS["switch_datasource"]["risk"],
                            "params": {"datasource_name": name},
                        }
                    ],
                }

    if any(word in stripped for word in ["查询", "统计", "分析", "看一下", "帮我看", "问数"]):
        return {
            "reply": "准备发起一次智能问数。",
            "reasoning": "命中了问数意图。",
            "actions": [
                {
                    "type": "ask_query",
                    "label": "执行智能问数",
                    "risk": ACTION_SPECS["ask_query"]["risk"],
                    "params": {"question": stripped},
                }
            ],
        }

    if any(word in stripped for word in ["安装", "skill", "技能"]):
        url_match = re.search(
            r"https?://github\.com/[^/\s]+/[^/\s]+/tree/[^/\s]+/[A-Za-z0-9._/-]+",
            stripped,
        )
        if url_match and any(item["type"] == "install_agent_skill" for item in context["allowed_actions"]):
            source = url_match.group(0).rstrip("，。,.")
            return {
                "reply": "准备安装外部 skill。该操作会写入本地 skill 目录，执行前需要确认来源可信。",
                "reasoning": "命中了外部 skill 安装意图，并提取到了 GitHub skill 来源。",
                "actions": [
                    {
                        "type": "install_agent_skill",
                        "label": "安装外部 Skill",
                        "risk": ACTION_SPECS["install_agent_skill"]["risk"],
                        "params": {"source": source},
                    }
                ],
            }

    return None


async def plan_agent_actions(message: str, context: dict) -> dict:
    selected_skill = select_skill(message, context)
    heuristic = _heuristic_plan(message, context) if should_use_heuristics(context) else None
    if heuristic:
        actions = apply_skill_action_constraints(heuristic["actions"], selected_skill)
        return {
            "skill": selected_skill,
            "reply": heuristic["reply"],
            "reasoning": heuristic["reasoning"],
            "requires_confirmation": _risk_for_actions(actions) != "low",
            "missing_fields": [],
            "actions": actions,
        }

    system_prompt = f"""你是企业网页 Agent 的规划器。你不能直接执行动作，只能输出结构化 JSON 计划。

必须遵守：
1. 只能从 allowed_actions 中选择动作类型。
2. 不要生成未授权动作。
3. 删除、创建、修改类动作要尽量要求确认。
4. 如果用户信息不足，返回 missing_fields。
5. 如果只是回答说明，不要生成 actions。

输出 JSON 结构：
{{
  "reply": "给用户的话",
  "reasoning": "简短规划依据",
  "missing_fields": ["缺少字段1"],
  "actions": [
    {{
      "type": "action_type",
      "label": "显示给用户的动作名",
      "params": {{}}
    }}
  ]
}}

当前上下文：
{json.dumps(context, ensure_ascii=False)}
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]
    try:
        raw = await chat_completion(messages, temperature=0.1)
        parsed = _extract_json(raw)
    except Exception:
        return {
            "reply": "我没法稳定规划这次操作。请改成更具体的指令，例如“打开数据源管理”或“查询今天各产线产量”。",
            "reasoning": "LLM 规划失败，进入兜底。",
            "requires_confirmation": False,
            "missing_fields": [],
            "actions": [],
        }

    allowed_types = {item["type"] for item in context["allowed_actions"]}
    normalized_actions: List[dict] = []
    for action in parsed.get("actions", []):
        action_type = action.get("type")
        if action_type not in allowed_types or action_type not in ACTION_SPECS:
            continue
        spec = ACTION_SPECS[action_type]
        params = action.get("params") or {}
        if action_type == "navigate":
            route = normalize_route(params.get("route") or params.get("path") or params.get("page"))
            if not route or not route_allowed(route, context["allowed_routes"]):
                continue
            params = {**params, "route": route}
        normalized_actions.append(
            {
                "type": action_type,
                "label": action.get("label") or spec["description"],
                "risk": spec["risk"],
                "params": params,
            }
        )

    normalized_actions = apply_skill_action_constraints(normalized_actions, selected_skill)

    return {
        "skill": selected_skill,
        "reply": parsed.get("reply") or "已生成执行计划。",
        "reasoning": parsed.get("reasoning") or "基于当前指令和权限生成。",
        "requires_confirmation": _risk_for_actions(normalized_actions) != "low",
        "missing_fields": parsed.get("missing_fields") or [],
        "actions": normalized_actions,
    }


def build_agent_context(
    role: str,
    route: str,
    datasource_id: int | None,
    datasource_name: str | None,
    datasource_names: List[str],
    agent_planner_mode: str = "llm_only",
) -> dict:
    skills = list_agent_skills()
    return {
        "current_route": route,
        "current_datasource_id": datasource_id,
        "current_datasource_name": datasource_name,
        "datasource_names": datasource_names,
        "agent_planner_mode": agent_planner_mode or "llm_only",
        "allowed_routes": [item for item, roles in ROUTE_PERMISSIONS.items() if role in roles],
        "route_aliases": {
            key: normalize_route(route)
            for key, route in ROUTE_MAP.items()
            if route_allowed(route, [item for item, roles in ROUTE_PERMISSIONS.items() if role in roles])
        },
        "allowed_actions": get_action_catalog(role),
        "skills": skills,
    }
