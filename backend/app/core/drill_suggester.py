import json
import re
from typing import Any, Dict, List

from app.core.llm import chat_completion


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        match = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if match:
            text = match[0].strip()
    return json.loads(text)


async def suggest_drill_actions(
    question: str,
    sql_query: str,
    columns: List[str],
    row: Dict[str, Any],
    selected_column: str,
) -> Dict[str, Any]:
    source_value = row.get(selected_column)
    if source_value in (None, "", "NULL"):
        return {"actions": [], "detail_action": None}

    system_prompt = f"""你是图表钻取建议器。请基于当前问数上下文，判断当前点击后是否适合继续钻取。

必须遵守：
1. 只能基于当前问题、当前 SQL、结果列、当前点击行来判断，不要假设完整 schema。
2. 如果没有明显合理的下一步，返回空数组。
3. 最多返回 3 个动作。
4. 优先选择更有业务意义的聚合口径，不要机械地下钻到“记录条数”。
5. 如果当前分析明显涉及产量、不良数量、金额、时长、效率、良率等业务量值，下一个问题也应优先延续这些量值口径。
6. 不要默认使用 COUNT(*)。只有当当前上下文明确在分析“记录数/出现次数/事件频次”，且没有更合适的业务量值时，才使用 COUNT(*)。
7. 如果当前 SQL 已经体现了某个业务指标口径（例如 SUM(NGCOUNT)、AVG(OEE)、SUM(OKCOUNT)），下钻问题应尽量保持同一指标口径继续分析。
8. 除了分析型钻取动作外，如果判断“查看详细记录信息”有价值，可以额外返回一个 detail_action。
9. detail_action 不是分析维度，而是查看当前点击点对应的明细记录。只有在当前点击点足够明确、且查看底层记录有业务意义时才返回。
10. 输出必须是 JSON，对象结构如下：
{{
  "actions": [
    {{
      "id": "唯一ID",
      "label": "按钮文案",
      "target_label": "下一层维度名",
      "question": "给系统继续问数的问题"
    }}
  ],
  "detail_action": {{
    "label": "查看明细",
    "question": "给系统继续问数的明细问题"
  }}
}}
"""

    user_prompt = json.dumps(
        {
            "question": question,
            "sql_query": sql_query,
            "selected_column": selected_column,
            "columns": columns,
            "row": row,
        },
        ensure_ascii=False,
    )

    try:
        raw = await chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        parsed = _extract_json(raw)
    except Exception:
        return {"actions": [], "detail_action": None}

    actions: List[Dict[str, Any]] = []
    for item in parsed.get("actions", [])[:3]:
        label = str(item.get("label") or "").strip()
        target_label = str(item.get("target_label") or "").strip()
        next_question = str(item.get("question") or "").strip()
        if not label or not target_label or not next_question:
            continue
        actions.append(
            {
                "id": item.get("id") or f"{selected_column}_{target_label}",
                "label": label,
                "action": "group_by",
                "source_dimension_id": selected_column.lower(),
                "source_dimension_label": selected_column,
                "source_column": selected_column,
                "source_value": source_value,
                "target_dimension_id": target_label.lower(),
                "target_dimension_label": target_label,
                "target_column": target_label,
                "question": next_question,
            }
        )
    detail_item = parsed.get("detail_action") or None
    detail_action = None
    if isinstance(detail_item, dict):
        detail_label = str(detail_item.get("label") or "").strip()
        detail_question = str(detail_item.get("question") or "").strip()
        if detail_label and detail_question:
            detail_action = {
                "id": f"{selected_column}_detail",
                "label": detail_label,
                "action": "show_rows",
                "source_dimension_id": selected_column.lower(),
                "source_dimension_label": selected_column,
                "source_column": selected_column,
                "source_value": source_value,
                "target_dimension_id": "detail",
                "target_dimension_label": "明细",
                "target_column": "detail",
                "question": detail_question,
            }

    return {"actions": actions, "detail_action": detail_action}
