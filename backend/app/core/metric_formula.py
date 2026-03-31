import json

from app.core.llm import chat_completion


async def generate_metric_formula(
    datasource_context: dict,
    name: str,
    definition: str,
    table_name: str | None = None,
    column_name: str | None = None,
) -> str:
    system_prompt = """你是数据指标建模助手。请根据数据源上下文和指标定义，生成一个简洁可执行的计算公式。

必须遵守：
1. 只返回公式文本，不要解释，不要 markdown。
2. 优先使用已知表名、字段名。
3. 聚合表达式保持简洁，例如 SUM(count)、AVG(ct)、COUNT(*)
"""
    user_prompt = {
        "datasource": datasource_context,
        "metric": {
            "name": name,
            "definition": definition,
            "table_name": table_name,
            "column_name": column_name,
        },
    }
    response = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    return response.strip().strip("`")
