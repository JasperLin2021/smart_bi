import json
import re

from app.core.llm import chat_completion
from app.schemas.datasource import ColumnSchema, TableSchema


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        match = re.findall(r"```(?:json)?\n(.*?)```", text, re.S)
        if match:
            text = match[0].strip()
    return json.loads(text)


async def generate_column_descriptions(
    datasource_name: str,
    table: TableSchema,
) -> tuple[TableSchema, int]:
    blank_columns = [col for col in table.columns if not (col.description or "").strip()]
    if not blank_columns:
        return table, 0

    payload = {
        "datasource_name": datasource_name,
        "table_name": table.name,
        "table_description": table.description,
        "columns": [
            {
                "name": col.name,
                "type": col.type,
                "description": col.description,
            }
            for col in table.columns
        ],
    }
    system_prompt = """你是数据建模助手。请为当前表中“说明为空”的字段补全简洁中文说明。

必须遵守：
1. 只为 description 为空的字段生成说明。
2. 已有 description 只作为参考，不要覆盖。
3. 每个说明尽量简短、准确、业务化，通常 4-12 个中文字符。
4. 如果不确定，使用中性描述，不要编造复杂业务含义。
5. 只返回 JSON，格式如下：
{
  "descriptions": {
    "COLUMN_NAME": "中文说明"
  }
}
"""
    raw = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    parsed = _extract_json(raw)
    descriptions = parsed.get("descriptions") or {}

    filled_count = 0
    updated_columns: list[ColumnSchema] = []
    for col in table.columns:
        if (col.description or "").strip():
            updated_columns.append(col)
            continue
        generated = str(descriptions.get(col.name) or "").strip()
        if generated:
            filled_count += 1
            updated_columns.append(
                ColumnSchema(name=col.name, type=col.type, description=generated)
            )
        else:
            updated_columns.append(col)

    return (
        TableSchema(
            name=table.name,
            description=table.description,
            columns=updated_columns,
        ),
        filled_count,
    )
