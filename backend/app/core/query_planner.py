import json
import re
from typing import Any

from app.core.llm import chat_completion


DEFAULT_PLAN = {
    "query_type": "aggregate",
    "primary_table": "",
    "dimensions": [],
    "metrics": [],
    "aggregation": "grouped_metric",
    "time_intent": False,
    "needs_join": False,
    "detail_preferred": False,
    "chart_preference": "bar",
}


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```" in text:
        match = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if match:
            text = match[0].strip()
    return json.loads(text)


def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = {**DEFAULT_PLAN, **plan}
    normalized["dimensions"] = [str(item) for item in normalized.get("dimensions", [])]
    normalized["metrics"] = [str(item) for item in normalized.get("metrics", [])]
    normalized["query_type"] = str(normalized.get("query_type") or "aggregate")
    normalized["primary_table"] = str(normalized.get("primary_table") or "")
    normalized["aggregation"] = str(normalized.get("aggregation") or "grouped_metric")
    normalized["chart_preference"] = str(normalized.get("chart_preference") or "bar")
    normalized["time_intent"] = bool(normalized.get("time_intent"))
    normalized["needs_join"] = bool(normalized.get("needs_join"))
    normalized["detail_preferred"] = bool(normalized.get("detail_preferred"))
    return normalized


def _rule_plan(question: str) -> dict[str, Any] | None:
    if re.search(r"(详细记录|明细|列出.*记录|所有.*记录|原始记录)", question):
        return {
            "query_type": "detail",
            "aggregation": "none",
            "detail_preferred": True,
            "chart_preference": "table",
        }
    if re.search(r"(top\s*\d+|前\d+|最高|最低|排名)", question, re.I):
        return {
            "query_type": "ranking",
            "aggregation": "grouped_metric",
            "chart_preference": "bar",
        }
    if re.search(r"(分布|构成|占比)", question):
        return {
            "query_type": "distribution",
            "aggregation": "grouped_metric",
            "chart_preference": "bar",
        }
    if re.search(r"(趋势|变化|对比|统计|平均|总数|数量)", question):
        return {
            "query_type": "aggregate",
            "aggregation": "grouped_metric",
            "chart_preference": "bar",
        }
    return None


async def plan_query(question: str, datasource=None) -> dict[str, Any]:
    rule_based = _rule_plan(question)
    if rule_based:
        return _normalize_plan(rule_based)

    metadata_prompt = getattr(datasource, "metadata_prompt", "") if datasource else ""
    metrics_prompt = getattr(datasource, "metrics_prompt", "") if datasource else ""
    system_prompt = """你是问数查询规划器。请先判断用户问题最适合的查询类型，并输出 JSON。

只允许输出 JSON，结构如下：
{
  "query_type": "detail|aggregate|distribution|ranking",
  "primary_table": "优先表名，可为空",
  "dimensions": ["维度字段或概念"],
  "metrics": ["指标字段或概念"],
  "aggregation": "none|grouped_metric",
  "time_intent": false,
  "needs_join": false,
  "detail_preferred": false,
  "chart_preference": "table|bar|line|pie"
}
"""
    if metadata_prompt:
        system_prompt += f"\n\n{metadata_prompt}"
    if metrics_prompt:
        system_prompt += f"\n\n{metrics_prompt}"

    raw = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    return _normalize_plan(_extract_json(raw))
