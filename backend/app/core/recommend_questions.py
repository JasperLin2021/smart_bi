import json
import re
from typing import Any

from app.core.llm import chat_completion
from app.schemas.datasource import SchemaMetadata


def _extract_json(raw: str) -> Any:
    text = raw.strip()
    if "```" in text:
        match = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if match:
            text = match[0].strip()
    return json.loads(text)


def _schema_payload(schema: SchemaMetadata | None) -> dict[str, Any] | None:
    if not schema:
        return None
    return {
        "tables": [
            {
                "name": table.name,
                "description": table.description,
                "columns": [
                    {
                        "name": column.name,
                        "type": column.type,
                        "description": column.description,
                    }
                    for column in table.columns[:40]
                ],
            }
            for table in schema.tables[:12]
        ],
        "relationships": [relationship.model_dump() for relationship in schema.relationships[:20]],
    }


def _clean_questions(items: list[Any], limit: int) -> list[str]:
    questions: list[str] = []
    seen: set[str] = set()
    for item in items:
        question = str(item or "").strip()
        question = re.sub(r"^\s*[-*•\d.、)）]+", "", question).strip()
        if not question:
            continue
        key = re.sub(r"\s+", "", question).lower()
        if key in seen:
            continue
        seen.add(key)
        questions.append(question[:120])
        if len(questions) >= limit:
            break
    return questions


async def generate_recommend_questions(
    *,
    datasource_name: str,
    source_type: str,
    metadata_prompt: str = "",
    metrics_prompt: str | None = None,
    schema: SchemaMetadata | None = None,
    limit: int = 6,
) -> list[str]:
    payload = {
        "datasource_name": datasource_name,
        "source_type": source_type,
        "metadata_prompt": metadata_prompt,
        "metrics_prompt": metrics_prompt,
        "schema": _schema_payload(schema),
        "limit": limit,
    }
    system_prompt = """你是 BI 数据产品助手。请基于数据源表结构和业务语义，生成适合显示在“智能问数入口”的推荐问题。

要求：
1. 问题必须能由当前数据源回答，不要编造不存在的业务域。
2. 覆盖趋势、排行、分布、异常/对比等常用分析场景。
3. 问题要面向业务用户，简洁自然，不写 SQL。
4. 避免过于泛泛的“分析数据”，优先包含可用字段、指标或时间范围。
5. 只返回 JSON，格式如下：
{
  "questions": ["问题1", "问题2"]
}
"""
    raw = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    parsed = _extract_json(raw)
    if isinstance(parsed, list):
        candidates = parsed
    else:
        candidates = parsed.get("questions") or []
    if not isinstance(candidates, list):
        return []
    return _clean_questions(candidates, max(1, min(limit, 10)))
