import httpx
import json
import re
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.llm_setting import LlmSetting


_llm_config_cache: dict | None = None
DASHSCOPE_PROVIDER_ALIASES = {"dashscope", "aliyun_bailian", "bailian", "aliyun"}
PI_PROVIDER_ALIASES = {"pi", "pi_mono", "pi-mono", "pimono"}

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
5. 如果元数据里给出了字段示例值，且用户问题中的业务名称能与某个示例值完整匹配，优先直接用该字段做等值过滤
6. 不要把一个完整的产线名、单元名、异常名、人名或料号拆成多个字段条件，除非元数据明确说明这些字段需要分别过滤
7. 如果某列的示例值为空或明显缺失，不要臆造该列的筛选条件
"""

DETAIL_QUERY_SUFFIX = """

如果用户明确要求详细记录、明细、列出所有记录、原始记录：
1. 优先选择最贴近业务事件的明细表，不要为了回答明细问题而优先查询汇总主表。
2. 除非用户明确要求统计汇总，否则不要使用 GROUP BY、SUM、COUNT、AVG 等聚合。
3. 优先返回能够直接体现事件明细的字段，而不是只返回主记录摘要字段。
4. 如果筛选条件中的字段已经存在于某张明细表中，优先直接查询该明细表。
"""

PLAN_QUERY_SUFFIXES = {
    "detail": """

当前查询规划类型：detail
1. 优先返回明细记录，避免无意义聚合。
2. 优先选择业务事件明细表，而不是主汇总表。
3. SELECT 应优先包含能解释单条记录的关键字段。
""",
    "aggregate": """

当前查询规划类型：aggregate
1. 优先围绕业务指标做聚合分析。
2. 需要明确分组维度和指标口径。
""",
    "distribution": """

当前查询规划类型：distribution
1. 重点回答不同维度上的业务量值分布。
2. 如果存在更有业务意义的量值字段，不要默认 COUNT(*)。
""",
    "ranking": """

当前查询规划类型：ranking
1. 结果必须显式排序。
2. 如果问题包含 Top/最高/最低/排名，优先返回排序后的有限结果。
3. 必须显式排序，且排序方向要与问题语义一致。
""",
}


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
    if provider in DASHSCOPE_PROVIDER_ALIASES:
        return {
            "provider": "dashscope",
            "base_url": settings.llm_dashscope_base,
            "api_key": settings.llm_dashscope_key,
            "model": settings.llm_dashscope_model,
            "temperature": 0.3,
            "agent_planner_mode": "llm_only",
        }
    if provider in PI_PROVIDER_ALIASES:
        return {
            "provider": "pi",
            "base_url": settings.llm_pi_base,
            "api_key": settings.llm_pi_key,
            "model": settings.llm_pi_model,
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
    _llm_config_cache = normalize_llm_config(config)


def normalize_llm_config(config: dict) -> dict:
    normalized = dict(config)
    provider = str(normalized.get("provider") or "").lower()
    if provider in DASHSCOPE_PROVIDER_ALIASES:
        provider = "dashscope"
    if provider in PI_PROVIDER_ALIASES:
        provider = "pi"
    normalized["provider"] = provider
    normalized["base_url"] = str(normalized.get("base_url") or "").rstrip("/")
    normalized["model"] = str(normalized.get("model") or "").strip()
    if provider == "dashscope":
        normalized["base_url"] = normalized["base_url"] or settings.llm_dashscope_base
        normalized["model"] = normalized["model"] or settings.llm_dashscope_model
    if provider == "pi":
        normalized["base_url"] = normalized["base_url"] or settings.llm_pi_base
        normalized["model"] = normalized["model"] or settings.llm_pi_model
    if provider == "gemini":
        normalized["base_url"] = normalized["base_url"] or settings.llm_gemini_base
        normalized["model"] = normalized["model"] or settings.llm_gemini_model
    return normalized


async def get_llm_config() -> dict:
    if _llm_config_cache:
        return _llm_config_cache
    db = SessionLocal()
    try:
        record = db.query(LlmSetting).first()
        if record:
            return normalize_llm_config({
                "provider": record.provider,
                "base_url": record.base_url,
                "api_key": record.api_key,
                "model": record.model,
                "temperature": record.temperature,
                "agent_planner_mode": record.agent_planner_mode or "llm_only",
            })
    finally:
        db.close()
    return normalize_llm_config(get_default_llm_config())


async def chat_completion(
    messages: list[dict],
    temperature: float | None = None,
    config_override: dict | None = None,
) -> str:
    config = normalize_llm_config(config_override or await get_llm_config())
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
    await chat_completion(messages, temperature=0, config_override=normalize_llm_config(config_override))
    return {"status": "ok", "message": "连接成功"}


def get_datasource_prompts(datasource) -> tuple[str, str, str]:
    """Get prompts from a DataSource object."""
    metadata_prompt = datasource.metadata_prompt or ""
    metrics_prompt = datasource.metrics_prompt or ""
    text2sql_prompt = datasource.text2sql_prompt or DEFAULT_TEXT2SQL_PROMPT
    return text2sql_prompt, metadata_prompt, metrics_prompt


async def generate_sql_query(
    question: str,
    datasource=None,
    context: str = "",
    query_plan: dict | None = None,
    metric_match: dict | None = None,
) -> dict:
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
    if metric_match:
        metric_name = (metric_match.get("name") or "").strip()
        metric_formula = (metric_match.get("formula") or "").strip()
        if metric_name or metric_formula:
            system_prompt += "\n\n本次问题命中的目标指标："
            if metric_name:
                system_prompt += metric_name
            if metric_formula:
                system_prompt += (
                    f"\n必须使用以下指标公式，不允许改写成其他口径：{metric_formula}"
                    "\n如果 SQL 中没有体现该公式或等价表达式，则答案无效。"
                )
    elif metrics_prompt:
        system_prompt += f"\n\n{metrics_prompt}"
    if datasource and getattr(datasource, "source_type", "") == "excel":
        system_prompt += EXCEL_TEXT2SQL_SUFFIX
    if re.search(r"(详细记录|明细|列出.*记录|所有.*记录|原始记录)", question):
        system_prompt += DETAIL_QUERY_SUFFIX
    if query_plan:
        query_type = str(query_plan.get("query_type") or "").strip().lower()
        if query_type in PLAN_QUERY_SUFFIXES:
            system_prompt += PLAN_QUERY_SUFFIXES[query_type]
        system_prompt += f"\n\n查询规划:{json.dumps(query_plan, ensure_ascii=False)}"

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
