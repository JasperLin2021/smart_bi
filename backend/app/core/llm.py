import httpx
import json
import re
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.llm_setting import LlmSetting


_llm_config_cache: dict | None = None

DEFAULT_TEXT2SQL_PROMPT = """你是SQL专家，根据用户问题生成标准SQL查询语句。

重要规则：
1. 如果用户问题涉及时间（如"近期"、"最近"、"本周"、"本月"、"今天"、"趋势"、"变化"等），SELECT必须包含时间字段（如 DATE(时间字段) as stat_date），以便展示时间趋势图
2. 对于趋势类问题，按时间分组（GROUP BY 时间字段）并排序（ORDER BY 时间字段）
3. 对于Top N类问题，按数值降序排序
4. 只输出纯SQL语句，不要包含任何解释或markdown格式"""

EXCEL_TEXT2SQL_SUFFIX = """

当前数据源运行在 DuckDB 上，请严格使用 DuckDB 兼容 SQL：
1. 不要使用 SQLite 风格的 DATE('now', '-1 month')、DATE(column, '-1 day') 这类两参数 DATE 写法
2. 当前日期请使用 CURRENT_DATE
3. 时间偏移请使用 INTERVAL，例如 CURRENT_DATE - INTERVAL '1 month'
4. 日期截断优先使用 CAST(时间字段 AS DATE)
"""

DETAIL_QUERY_SUFFIX = """

如果用户明确要求详细记录、明细、列出所有记录、原始记录：
1. 优先选择最贴近业务事件的明细表，不要为了回答明细问题而优先查询汇总主表。
2. 除非用户明确要求统计汇总，否则不要使用 GROUP BY、SUM、COUNT、AVG 等聚合。
3. 优先返回能够直接体现事件明细的字段，而不是只返回主记录摘要字段。
4. 如果筛选条件中的字段已经存在于某张明细表中，优先直接查询该明细表。
"""


def get_default_llm_config() -> dict:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return {
            "provider": "openai",
            "base_url": settings.llm_openai_base,
            "api_key": settings.llm_openai_key,
            "model": settings.llm_openai_model,
            "temperature": 0.3,
            "agent_planner_mode": "llm_only",
        }
    if provider == "moonshot":
        return {
            "provider": "moonshot",
            "base_url": settings.llm_moonshot_base,
            "api_key": settings.llm_moonshot_key,
            "model": settings.llm_moonshot_model,
            "temperature": 0.3,
            "agent_planner_mode": "llm_only",
        }
    if provider == "deepseek":
        return {
            "provider": "deepseek",
            "base_url": settings.llm_deepseek_base,
            "api_key": settings.llm_deepseek_key,
            "model": settings.llm_deepseek_model,
            "temperature": 0.3,
            "agent_planner_mode": "llm_only",
        }
    if provider == "gemini":
        return {
            "provider": "gemini",
            "base_url": settings.llm_gemini_base,
            "api_key": settings.llm_gemini_key,
            "model": settings.llm_gemini_model,
            "temperature": 0.3,
            "agent_planner_mode": "llm_only",
        }
    return {
        "provider": "custom",
        "base_url": settings.llm_api_base,
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
        "temperature": 0.3,
        "agent_planner_mode": "llm_only",
    }


def set_llm_config_cache(config: dict):
    global _llm_config_cache
    _llm_config_cache = config


async def get_llm_config() -> dict:
    if _llm_config_cache:
        return _llm_config_cache
    db = SessionLocal()
    try:
        record = db.query(LlmSetting).first()
        if record:
            return {
                "provider": record.provider,
                "base_url": record.base_url,
                "api_key": record.api_key,
                "model": record.model,
                "temperature": record.temperature,
                "agent_planner_mode": record.agent_planner_mode or "llm_only",
            }
    finally:
        db.close()
    return get_default_llm_config()


async def chat_completion(
    messages: list[dict],
    temperature: float | None = None,
    config_override: dict | None = None,
) -> str:
    config = config_override or await get_llm_config()
    actual_temperature = config.get("temperature", 0.3) if temperature is None else temperature
    async with httpx.AsyncClient(timeout=30) as client:
        if config["provider"] == "gemini":
            combined = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            payload = {
                "contents": [{"role": "user", "parts": [{"text": combined}]}],
                "generationConfig": {"temperature": actual_temperature},
            }
            response = await client.post(
                f"{config['base_url']}/models/{config['model']}:generateContent",
                params={"key": config["api_key"]},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": actual_temperature,
        }
        headers = {}
        if config["api_key"]:
            headers["Authorization"] = f"Bearer {config['api_key']}"
        response = await client.post(
            f"{config['base_url']}/chat/completions",
            json=payload,
            headers=headers,
        )
        if response.status_code != 200:
            print(f"LLM API Error: {response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def test_llm_connection(config_override: dict) -> dict:
    messages = [
        {"role": "system", "content": "Reply with exactly: pong"},
        {"role": "user", "content": "ping"},
    ]
    await chat_completion(messages, temperature=0, config_override=config_override)
    return {"status": "ok", "message": "连接成功"}


def get_datasource_prompts(datasource) -> tuple[str, str, str]:
    """Get prompts from a DataSource object."""
    metadata_prompt = datasource.metadata_prompt or ""
    metrics_prompt = datasource.metrics_prompt or ""
    text2sql_prompt = datasource.text2sql_prompt or DEFAULT_TEXT2SQL_PROMPT
    return text2sql_prompt, metadata_prompt, metrics_prompt


async def generate_sql_query(question: str, datasource=None, context: str = "") -> dict:
    """生成SQL查询语句，基于数据源的元数据"""
    if datasource:
        text2sql_prompt, metadata_prompt, metrics_prompt = get_datasource_prompts(datasource)
    else:
        text2sql_prompt = DEFAULT_TEXT2SQL_PROMPT
        metadata_prompt = ""
        metrics_prompt = ""

    system_prompt = text2sql_prompt
    if metadata_prompt:
        system_prompt += f"\n\n{metadata_prompt}"
    if metrics_prompt:
        system_prompt += f"\n\n{metrics_prompt}"
    if datasource and getattr(datasource, "source_type", "") == "excel":
        system_prompt += EXCEL_TEXT2SQL_SUFFIX
    if re.search(r"(详细记录|明细|列出.*记录|所有.*记录|原始记录)", question):
        system_prompt += DETAIL_QUERY_SUFFIX

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"问题:{question}\n上下文:{context}"},
    ]
    content = await chat_completion(messages, temperature=0.2)

    sql = content.strip()
    if "```" in content:
        matches = re.findall(r"```(?:sql)?\n(.*?)```", content, re.S)
        if matches:
            sql = matches[0].strip()

    return {"raw": content, "sql": sql}


async def generate_summary(question: str, result: dict) -> str:
    messages = [
        {
            "role": "system",
            "content": "你是数据分析助手，输出简洁的中文分析总结。",
        },
        {"role": "user", "content": f"问题:{question}\n结果:{result}"},
    ]
    return await chat_completion(messages, temperature=0.3)


async def chat(question: str) -> str:
    """闲聊模式，直接与AI对话"""
    messages = [
        {
            "role": "system",
            "content": "你是一个友好的AI助手，可以帮助用户回答问题、聊天。请用中文简洁回复。",
        },
        {"role": "user", "content": question},
    ]
    return await chat_completion(messages)
