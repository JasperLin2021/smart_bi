import json
import re
from typing import Any, Awaitable, Callable

from app.core.llm import chat_completion
from app.core.sql_guard import detect_excel_join_risk


DANGEROUS_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|merge|call|grant|revoke|copy|attach|detach|vacuum)\b",
    re.I,
)
TraceCallback = Callable[[dict[str, Any]], Awaitable[None]]
CHART_TYPES = {"line", "bar", "horizontal_bar", "area", "pie", "donut", "scatter", "table", "kpi", "combo"}
CHART_LAYOUTS = {"single", "tabs_by_field"}
CHART_SORT_ORDERS = {"none", "asc", "desc"}


def _trace(stage: str, status: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"stage": stage, "status": status, "message": message}
    if detail:
        item["detail"] = detail
    return item


async def _append_trace(
    trace: list[dict[str, Any]],
    item: dict[str, Any],
    on_trace: TraceCallback | None = None,
) -> None:
    trace.append(item)
    if on_trace:
        await on_trace(item)


def _extract_fenced_block(raw: str, language: str | None = None) -> str:
    text = raw.strip()
    if "```" not in text:
        return text
    lang = language or r"[a-zA-Z0-9_-]*"
    pattern = rf"```(?:{lang})?\s*\n?(.*?)```"
    matches = re.findall(pattern, text, re.S)
    return matches[0].strip() if matches else text


def _extract_json(raw: str) -> dict[str, Any]:
    text = _extract_fenced_block(raw, "json")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        value = json.loads(match.group(0))
    return value if isinstance(value, dict) else {}


def _extract_sql(raw: str) -> str:
    text = _extract_fenced_block(raw, "sql").strip()
    text = re.sub(r"^\s*SQL\s*[:：]\s*", "", text, flags=re.I)
    return text.strip()


def _strip_sql_comments(sql: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n\r]*", " ", without_blocks)


def assert_read_only_sql(sql: str) -> str:
    candidate = sql.strip()
    candidate = re.sub(r";+\s*$", "", candidate).strip()
    if not candidate:
        raise ValueError("探索模式只允许生成非空只读 SQL")
    if ";" in candidate:
        raise ValueError("探索模式只允许生成单条只读 SQL")

    sql_without_comments = _strip_sql_comments(candidate)
    if not re.match(r"^\s*(select|with)\b", sql_without_comments, re.I):
        raise ValueError("探索模式只允许生成只读 SELECT SQL")
    if DANGEROUS_SQL_PATTERN.search(sql_without_comments):
        raise ValueError("探索模式只允许生成只读 SQL，不允许包含写入、DDL 或运维语句")
    return candidate


def _compact_json(value: Any, limit: int = 4000) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else f"{text[:limit]}\n...(已截断)"


def infer_sql_dialect(datasource: Any) -> str:
    source_type = str(getattr(datasource, "source_type", "") or "").lower()
    database_url = str(getattr(datasource, "database_url", "") or "").lower()
    url_driver = database_url.split(":", 1)[0]

    if source_type == "excel":
        return "DuckDB"
    if "postgresql" in url_driver or database_url.startswith("postgres://"):
        return "PostgreSQL"
    if "mysql" in url_driver or "mariadb" in url_driver:
        return "MySQL"
    if "sqlite" in url_driver:
        return "SQLite"
    if "mssql" in url_driver or "sqlserver" in url_driver:
        return "SQL Server"
    if "oracle" in url_driver:
        return "Oracle"
    return "数据库默认方言"


def _dialect_repair_hint(dialect: str) -> str:
    if dialect == "PostgreSQL":
        return (
            "PostgreSQL 日期偏移示例：NOW() - INTERVAL '30 days'；"
            "不要使用 MySQL 的 DATE_SUB(NOW(), INTERVAL 30 DAY)。"
        )
    if dialect == "DuckDB":
        return "DuckDB 日期偏移示例：CURRENT_DATE - INTERVAL '30 days'。"
    if dialect == "SQLite":
        return "SQLite 日期偏移示例：datetime('now', '-30 days')。"
    return "请严格使用当前数据源 SQL 方言支持的函数和日期写法。"


def _build_datasource_context(datasource: Any) -> str:
    parts = [
        f"数据源名称：{getattr(datasource, 'name', '未命名数据源')}",
        f"数据源类型：{getattr(datasource, 'source_type', 'database') or 'database'}",
        f"SQL 方言：{infer_sql_dialect(datasource)}",
    ]
    metadata_prompt = getattr(datasource, "metadata_prompt", "") or ""
    schema_metadata = getattr(datasource, "schema_metadata", None)
    metrics_prompt = getattr(datasource, "metrics_prompt", "") or ""
    if metadata_prompt:
        parts.append(f"元数据提示：\n{metadata_prompt}")
    if schema_metadata:
        parts.append(f"结构化 Schema：\n{_compact_json(schema_metadata)}")
    if metrics_prompt:
        parts.append(f"指标口径：\n{metrics_prompt}")
    return "\n\n".join(parts)


def _normalize_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in items:
            items.append(text)
    return items[:6]


def _normalize_refinement_actions(value: Any, question: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    actions: list[dict[str, str]] = []
    for item in value:
        label = ""
        refined_question = ""
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("title") or "").strip()
            refined_question = str(item.get("question") or item.get("prompt") or "").strip()
        else:
            label = str(item or "").strip()
        if not label and refined_question:
            label = refined_question
        if label and not refined_question:
            refined_question = f"{question}，并明确：{label.rstrip('？?')}"
        if not label or not refined_question:
            continue
        action = {"label": label[:28], "question": refined_question}
        if action not in actions:
            actions.append(action)
    return actions[:4]


def _normalize_plan(raw: str, question: str) -> dict[str, Any]:
    try:
        parsed = _extract_json(raw)
    except Exception:
        parsed = {}
    objective = str(parsed.get("objective") or question).strip()
    steps = parsed.get("steps") if isinstance(parsed.get("steps"), list) else []
    assumptions = _normalize_text_list(parsed.get("assumptions"))
    risk_flags = _normalize_text_list(parsed.get("risk_flags"))
    suggested_refinements = _normalize_refinement_actions(parsed.get("suggested_refinements"), question)
    if parsed.get("needs_clarification"):
        reason = str(parsed.get("reason") or "问题描述不完整").strip()
        if reason and not assumptions:
            assumptions.append(f"{reason}，已基于数据源元数据使用合理默认口径继续查询。")
        if "question_ambiguous" not in risk_flags:
            risk_flags.append("question_ambiguous")
        if not suggested_refinements:
            suggested_refinements = _normalize_refinement_actions(parsed.get("questions"), question)
    confidence = str(parsed.get("confidence") or ("medium" if assumptions or risk_flags else "high")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    return {
        "objective": objective,
        "steps": [str(item) for item in steps],
        "expected_output": str(parsed.get("expected_output") or "table").strip(),
        "assumptions": assumptions,
        "risk_flags": risk_flags,
        "suggested_refinements": suggested_refinements,
        "confidence": confidence,
    }


def _agent_notes_from_plan(plan: dict[str, Any]) -> dict[str, Any] | None:
    assumptions = _normalize_text_list(plan.get("assumptions"))
    risk_flags = _normalize_text_list(plan.get("risk_flags"))
    suggested_refinements = _normalize_refinement_actions(plan.get("suggested_refinements"), "")
    confidence = str(plan.get("confidence") or "high").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    if not assumptions and not risk_flags and not suggested_refinements:
        return None
    return {
        "assumptions": assumptions,
        "risk_flags": risk_flags,
        "suggested_refinements": suggested_refinements,
        "confidence": confidence,
    }


def _is_numeric_value(value: Any) -> bool:
    if isinstance(value, bool) or value is None or value == "":
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _is_date_like_field(column: str, rows: list[dict[str, Any]]) -> bool:
    lower = column.lower()
    if any(token in lower for token in ("date", "time", "day", "month", "week", "year", "datetime")):
        return True
    for row in rows[:10]:
        value = row.get(column)
        if value is None:
            continue
        if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", str(value)):
            return True
    return False


def _resolve_column(value: Any, columns: list[str]) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate in columns:
        return candidate
    lowered = candidate.lower()
    return next((column for column in columns if column.lower() == lowered), None)


def _preferred_facet_field(columns: list[str]) -> str | None:
    facet_tokens = ("alarm", "error", "code", "type", "category")
    return next(
        (column for column in columns if any(token in column.lower() for token in facet_tokens)),
        columns[0] if columns else None,
    )


def _preferred_series_field(columns: list[str]) -> str | None:
    series_tokens = ("equipment", "device", "machine", "station", "line")
    return next(
        (column for column in columns if any(token in column.lower() for token in series_tokens)),
        columns[0] if columns else None,
    )


def _is_identifier_like_column(column: str) -> bool:
    identifier_tokens = ("id", "code", "type", "name", "alarm", "error", "equipment", "device", "machine")
    lower = column.lower()
    return any(token in lower for token in identifier_tokens)


def infer_agentic_chart_spec(question: str, result: dict[str, Any]) -> dict[str, Any]:
    columns = [str(column) for column in result.get("columns", [])]
    rows = result.get("rows", []) if isinstance(result.get("rows"), list) else []
    if not columns or not rows:
        return {
            "chart_type": "table",
            "title": question[:80],
            "x_field": None,
            "y_field": None,
            "series_fields": [],
            "layout": "single",
            "facet_field": None,
            "sort_order": "none",
            "reason": "结果为空或缺少列信息，使用明细表兜底。",
        }

    numeric_columns = [
        column
        for column in columns
        if any(_is_numeric_value(row.get(column)) for row in rows[:20])
    ]
    date_columns = [column for column in columns if _is_date_like_field(column, rows)]
    value_patterns = ("count", "total", "sum", "times", "amount", "num", "qty", "value", "occurrence")
    y_field = next(
        (column for column in numeric_columns if any(token in column.lower() for token in value_patterns)),
        numeric_columns[0] if numeric_columns else None,
    )
    x_field = date_columns[0] if date_columns else next((column for column in columns if column != y_field), columns[0])
    dimension_fields = [
        column
        for column in columns
        if column not in {x_field, y_field}
        and (column not in numeric_columns or _is_identifier_like_column(column))
    ]
    question_lower = question.lower()
    wants_trend = bool(date_columns) or any(token in question_lower for token in ("趋势", "trend", "走势", "按天", "按月"))

    if wants_trend and x_field and y_field:
        layout = "single"
        facet_field = None
        series_fields = dimension_fields[:1]
        if len(dimension_fields) >= 2:
            layout = "tabs_by_field"
            facet_field = dimension_fields[0]
            series_fields = [dimension_fields[1]]
        return {
            "chart_type": "line",
            "title": question[:80],
            "x_field": x_field,
            "y_field": y_field,
            "series_fields": series_fields,
            "layout": layout,
            "facet_field": facet_field,
            "sort_order": "none",
            "reason": "识别到时间字段和趋势问题，使用折线图展示随时间变化。",
        }

    if not y_field:
        return {
            "chart_type": "table",
            "title": question[:80],
            "x_field": columns[0],
            "y_field": None,
            "series_fields": [],
            "layout": "single",
            "facet_field": None,
            "sort_order": "none",
            "reason": "未识别到数值指标，使用明细表兜底。",
        }

    unique_x = len({str(row.get(x_field)) for row in rows}) if x_field else 0
    chart_type = "pie" if unique_x and unique_x <= 6 and not dimension_fields else "bar"
    return {
        "chart_type": chart_type,
        "title": question[:80],
        "x_field": x_field,
        "y_field": y_field,
        "series_fields": dimension_fields[:1],
        "layout": "single",
        "facet_field": None,
        "sort_order": "desc" if chart_type == "bar" else "none",
        "reason": "按结果列结构自动选择分类对比图。",
    }


def _normalize_chart_spec(raw: str, question: str, result: dict[str, Any]) -> dict[str, Any]:
    fallback = infer_agentic_chart_spec(question, result)
    columns = [str(column) for column in result.get("columns", [])]
    rows = result.get("rows", []) if isinstance(result.get("rows"), list) else []
    try:
        parsed = _extract_json(raw)
    except Exception:
        return fallback

    chart_type = str(parsed.get("chart_type") or fallback["chart_type"]).strip().lower()
    if chart_type not in CHART_TYPES:
        chart_type = fallback["chart_type"]
    if chart_type in {"donut"}:
        chart_type = "pie"

    x_field = _resolve_column(parsed.get("x_field"), columns) or fallback.get("x_field")
    y_field = _resolve_column(parsed.get("y_field"), columns) or fallback.get("y_field")
    facet_field = _resolve_column(parsed.get("facet_field"), columns) or fallback.get("facet_field")
    raw_series = parsed.get("series_fields") if isinstance(parsed.get("series_fields"), list) else []
    series_fields = []
    for item in raw_series:
        column = _resolve_column(item, columns)
        if column and column not in {x_field, y_field, facet_field} and column not in series_fields:
            series_fields.append(column)
    if not series_fields:
        series_fields = list(fallback.get("series_fields") or [])

    layout = str(parsed.get("layout") or fallback["layout"]).strip().lower()
    if layout not in CHART_LAYOUTS:
        layout = fallback["layout"]
    if layout == "tabs_by_field" and not facet_field:
        layout = "single"
    if chart_type in {"pie", "table", "kpi"}:
        layout = "single"
        facet_field = None
        series_fields = []

    sort_order = str(parsed.get("sort_order") or fallback["sort_order"]).strip().lower()
    if sort_order not in CHART_SORT_ORDERS:
        sort_order = fallback["sort_order"]

    numeric_columns = [
        column
        for column in columns
        if any(_is_numeric_value(row.get(column)) for row in rows[:20])
    ]
    dimension_candidates = [
        column
        for column in columns
        if column not in {x_field, y_field}
        and (column not in numeric_columns or _is_identifier_like_column(column))
    ]
    if chart_type in {"line", "area"} and x_field and y_field and len(dimension_candidates) >= 2:
        if not facet_field:
            unused_dimensions = [column for column in dimension_candidates if column not in series_fields]
            facet_field = _preferred_facet_field(unused_dimensions or dimension_candidates)
        if not series_fields:
            series_field = _preferred_series_field([column for column in dimension_candidates if column != facet_field])
            series_fields = [series_field] if series_field else []
        if facet_field and series_fields:
            layout = "tabs_by_field"
            series_fields = [column for column in series_fields if column != facet_field]

    return {
        "chart_type": chart_type,
        "title": str(parsed.get("title") or fallback.get("title") or question[:80]).strip()[:128],
        "x_field": x_field,
        "y_field": y_field,
        "series_fields": series_fields,
        "layout": layout,
        "facet_field": facet_field,
        "sort_order": sort_order,
        "reason": str(parsed.get("reason") or fallback.get("reason") or "").strip()[:300],
    }


async def build_agentic_chart_spec(
    question: str,
    result: dict[str, Any],
    llm_model: str | None = None,
    llm_config: dict[str, Any] | None = None,
    on_trace: TraceCallback | None = None,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    columns = [str(column) for column in result.get("columns", [])]
    rows = result.get("rows", []) if isinstance(result.get("rows"), list) else []
    sample_rows = rows[:20]
    if not llm_model and llm_config:
        llm_model = str(llm_config.get("model") or "").strip() or None

    try:
        raw = await chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是 Agentic 数据可视化规划器。根据用户问题和 SQL 结果结构选择最合适的图表。"
                        "只输出 JSON，不要 markdown。字段：chart_type、title、x_field、y_field、"
                        "series_fields、layout、facet_field、sort_order、reason。"
                        "chart_type 只能是 line、bar、horizontal_bar、area、pie、scatter、table、kpi。"
                        "layout 只能是 single 或 tabs_by_field。"
                        "多维时间趋势优先使用 line；如果同时有 alarmcode 和 equipmentid 等多级维度，"
                        "优先用 tabs_by_field，让高层维度做 facet_field，设备等明细维度做 series_fields。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n"
                        f"结果列：{json.dumps(columns, ensure_ascii=False)}\n"
                        f"总行数：{len(rows)}\n"
                        f"样例数据：{_compact_json(sample_rows, limit=3000)}"
                    ),
                },
            ],
            temperature=0,
            config_override=llm_config,
        )
        chart_spec = _normalize_chart_spec(raw, question, result)
        detail = {"chart_spec": chart_spec}
        if llm_model:
            detail["model"] = llm_model
        await _append_trace(trace, _trace("chart_plan", "success", "已生成图表规划", detail), on_trace)
    except Exception as exc:
        chart_spec = infer_agentic_chart_spec(question, result)
        detail = {"chart_spec": chart_spec, "error": str(exc) or exc.__class__.__name__}
        if llm_model:
            detail["model"] = llm_model
        await _append_trace(trace, _trace("chart_plan", "warning", "图表规划失败，已使用规则兜底", detail), on_trace)

    return {"chart_spec": chart_spec, "trace": trace}


async def _plan(
    question: str,
    datasource_context: str,
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "你是 Agentic NL2SQL 规划器。根据数据源上下文为用户问题制定简短查询计划。"
                    "即使问题较宽泛，也要基于可用元数据给出合理的查询目标和步骤，不要反问用户。"
                    "如果问题缺少时间范围、指标口径或分析维度，不要阻塞执行；"
                    "请写入 assumptions、risk_flags、suggested_refinements 和 confidence，"
                    "用于前端展示默认假设和快捷改写建议。"
                    "返回 objective、steps、expected_output、assumptions、risk_flags、suggested_refinements、confidence。"
                    "suggested_refinements 每项包含 label 和 question。"
                    "只输出 JSON。"
                ),
            },
            {"role": "user", "content": f"问题：{question}\n\n数据源上下文：\n{datasource_context}"},
        ],
        temperature=0,
        config_override=llm_config,
    )
    return _normalize_plan(raw, question)


async def _generate_sql(
    question: str,
    datasource_context: str,
    plan: dict[str, Any],
    feedback: str = "",
    llm_config: dict[str, Any] | None = None,
) -> str:
    feedback_text = f"\n\n上一版问题：{feedback}\n请修复后只输出最终 SQL。" if feedback else ""
    raw = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "你是谨慎的 NL2SQL Agent。只能生成单条只读 SELECT SQL。"
                    "必须遵循数据源上下文中的 SQL 方言。"
                    "不得输出 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE、TRUNCATE、CALL 等语句。"
                    "不要使用 markdown，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题：{question}\n\n查询计划：{json.dumps(plan, ensure_ascii=False)}"
                    f"\n\n数据源上下文：\n{datasource_context}{feedback_text}"
                ),
            },
        ],
        temperature=0,
        config_override=llm_config,
    )
    return _extract_sql(raw)


def _validate_agentic_sql(datasource: Any, sql: str) -> str:
    safe_sql = assert_read_only_sql(sql)
    if getattr(datasource, "source_type", "") == "excel":
        risk = detect_excel_join_risk(getattr(datasource, "database_url", ""), safe_sql)
        if risk:
            raise ValueError(f"{risk['message']} {risk['hint']}")
    return safe_sql


async def build_agentic_nl2sql(
    question: str,
    datasource: Any,
    llm_model: str | None = None,
    llm_config: dict[str, Any] | None = None,
    extra_context: str | None = None,
    max_repairs: int = 2,
    on_trace: TraceCallback | None = None,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    datasource_context = _build_datasource_context(datasource)
    if extra_context:
        datasource_context = f"{datasource_context}\n\n运行时探测证据：\n{extra_context.strip()}"
    if not llm_model and llm_config:
        llm_model = str(llm_config.get("model") or "").strip() or None
    context_detail = {
        "datasource": getattr(datasource, "name", "未命名数据源"),
        "source_type": getattr(datasource, "source_type", "database") or "database",
        "dialect": infer_sql_dialect(datasource),
    }
    if llm_model:
        context_detail["model"] = llm_model
    await _append_trace(trace, _trace("context", "success", "已读取数据源元数据", context_detail), on_trace)

    plan = await _plan(question, datasource_context, llm_config=llm_config)
    await _append_trace(trace, _trace("plan", "success", "已生成查询计划", {"plan": plan}), on_trace)
    agent_notes = _agent_notes_from_plan(plan)
    if agent_notes:
        await _append_trace(
            trace,
            _trace("assumption", "warning", "问题信息不完整，已按默认假设继续查询", {"agent_notes": agent_notes}),
            on_trace,
        )

    last_error = ""
    feedback = ""
    for attempt in range(max_repairs + 1):
        stage = "sql_generate" if attempt == 0 else "sql_fix"
        sql = await _generate_sql(
            question,
            datasource_context,
            plan,
            feedback=feedback,
            llm_config=llm_config,
        )
        try:
            safe_sql = _validate_agentic_sql(datasource, sql)
            await _append_trace(trace, _trace(stage, "success", "已生成安全 SQL", {"sql": safe_sql}), on_trace)
            return {"sql_query": safe_sql, "plan": plan, "trace": trace, "agent_notes": agent_notes}
        except ValueError as exc:
            last_error = str(exc)
            await _append_trace(trace, _trace(stage, "error", last_error, {"sql": sql}), on_trace)
            feedback = last_error

    raise ValueError(last_error or "探索模式 SQL 生成失败")


async def repair_agentic_sql_after_execution_error(
    question: str,
    datasource: Any,
    plan: dict[str, Any],
    failed_sql: str,
    execution_error: str,
    llm_model: str | None = None,
    llm_config: dict[str, Any] | None = None,
    max_repairs: int = 1,
    on_trace: TraceCallback | None = None,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    datasource_context = _build_datasource_context(datasource)
    if not llm_model and llm_config:
        llm_model = str(llm_config.get("model") or "").strip() or None
    dialect = infer_sql_dialect(datasource)
    compact_error = _compact_json(str(execution_error), limit=2000)
    base_feedback = (
        "数据库执行上一版 SQL 失败，请根据错误信息修复 SQL 后重试。\n"
        f"SQL 方言：{dialect}\n"
        f"方言提示：{_dialect_repair_hint(dialect)}\n"
        f"失败 SQL：\n{failed_sql}\n"
        f"执行错误：\n{compact_error}"
    )

    last_error = ""
    feedback = base_feedback
    for attempt in range(max_repairs + 1):
        stage = "sql_execute_fix" if attempt == 0 else "sql_execute_fix_retry"
        sql = await _generate_sql(
            question,
            datasource_context,
            plan,
            feedback=feedback,
            llm_config=llm_config,
        )
        detail = {
            "sql": sql,
            "failed_sql": failed_sql,
            "execution_error": compact_error,
            "dialect": dialect,
        }
        if llm_model:
            detail["model"] = llm_model
        try:
            safe_sql = _validate_agentic_sql(datasource, sql)
            detail["sql"] = safe_sql
            await _append_trace(trace, _trace(stage, "success", "已根据执行错误修复 SQL", detail), on_trace)
            return {"sql_query": safe_sql, "trace": trace}
        except ValueError as exc:
            last_error = str(exc)
            await _append_trace(trace, _trace(stage, "error", last_error, detail), on_trace)
            feedback = f"{base_feedback}\n\n修复后的 SQL 仍未通过安全检查：{last_error}"

    raise ValueError(last_error or "探索模式 SQL 执行错误修复失败")
