import json
import re
from typing import Any

import sqlglot
from sqlglot import exp


def _parse_metrics_prompt(metrics_prompt: str | None) -> list[dict[str, str]]:
    if not metrics_prompt:
        return []

    metrics: list[dict[str, str]] = []
    for raw_line in metrics_prompt.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        name_part, _, rest = body.partition(":")
        name = name_part.strip()
        if not name:
            continue
        formula = ""
        formula_marker = "计算公式："
        if formula_marker in rest:
            formula = rest.split(formula_marker, 1)[1].strip()
        metrics.append(
            {
                "name": name,
                "formula": formula,
                "raw": line,
            }
        )
    return metrics


def match_metric_from_question(question: str, datasource: Any) -> dict[str, str] | None:
    """降级路径：无 db 时从数据源 metrics_prompt 快照做文本匹配（保持旧签名兼容）。"""
    metrics_prompt = getattr(datasource, "metrics_prompt", None)
    metrics = _parse_metrics_prompt(metrics_prompt)
    if not metrics:
        return None

    for metric in metrics:
        name = metric["name"]
        if name and name in question:
            return metric

    lowered = question.lower()
    for metric in metrics:
        name = metric["name"].lower()
        tokens = [token for token in re.split(r"[\s_/()-]+", name) if token]
        if tokens and all(token in lowered for token in tokens):
            return metric

    return None


def _metric_name_aliases(name: str) -> list[str]:
    """提取指标名括号内的别名，如「订单金额(含税)」-> ['含税']，支持中英文括号。"""
    aliases = [item.strip() for item in re.findall(r"[（(]([^)）]+)[)）]", name) if item.strip()]
    return list(dict.fromkeys(aliases))


def _metric_question_explicit(metric: Any, lowered: str) -> bool:
    """问题是否显式完整引用了该指标（原名或括号别名）。"""
    name = str(metric.name or "").strip().lower()
    if name and name in lowered:
        return True
    return any(
        alias and alias.lower() in lowered
        for alias in _metric_name_aliases(str(metric.name or ""))
    )


def _metric_substring_hit(name_lower: str, lowered: str) -> bool:
    """中文连续片段（>=3 字）子串命中，缓解「订单数量」命不中「月订单数量」的分词缺口。

    仅对纯中文片段生成子串；中英混合片段由上层按整词/分词判断，避免切碎英文产生噪音。
    """
    for part in re.split(r"[^a-z0-9\u4e00-\u9fff]+", name_lower):
        if not part or re.search(r"[a-z0-9]", part) or not re.search(r"[\u4e00-\u9fff]", part):
            continue
        for i in range(len(part)):
            for j in range(i + 3, len(part) + 1):
                if part[i:j] in lowered:
                    return True
    return False


def _metric_fixed_filters(metric: Any) -> list[dict]:
    """提取指标计算配置中的固定筛选（field 与 value 均非空），如 order_status='delivered'。"""
    config = getattr(metric, "calculation_config", None) or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except Exception:
            config = {}
    filters = config.get("filters") if isinstance(config, dict) else None
    if not isinstance(filters, list):
        return []
    result: list[dict] = []
    for item in filters:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        value = item.get("value")
        if field and value not in (None, ""):
            result.append(
                {
                    "logic": str(item.get("logic") or "AND").upper(),
                    "field": field,
                    "operator": str(item.get("operator") or "="),
                    "value": value,
                }
            )
    return result


def _metric_filters_to_sql(filters: list[dict]) -> str:
    """把固定筛选转成 WHERE 条件片段，如 orders.order_status = 'delivered'。"""
    parts: list[str] = []
    for item in filters:
        field = item["field"]
        operator = str(item.get("operator") or "=")
        value = item["value"]
        if isinstance(value, str):
            rendered = f"{field} {operator} '{value.replace(chr(39), chr(39) * 2)}'"
        elif isinstance(value, bool):
            rendered = f"{field} {operator} {str(value).lower()}"
        else:
            rendered = f"{field} {operator} {value}"
        parts.append(rendered)
    return " AND ".join(parts)


def metric_caliber_formula(metric: Any) -> str:
    """指标完整口径：公式 + 固定筛选。

    如「月订单数量」= COUNT(orders.order_id) + 固定筛选 order_status='delivered'，
    返回 COUNT(orders.order_id) WHERE orders.order_status = 'delivered'，
    供 prompt 注入与 AST 校验同时约束口径，避免 LLM 漏掉指标自带筛选。
    """
    formula = str(getattr(metric, "formula", "") or "").strip()
    filters_sql = _metric_filters_to_sql(_metric_fixed_filters(metric))
    if formula and filters_sql:
        return f"{formula} WHERE {filters_sql}"
    return formula


def _metric_match_score(metric: Any, question: str, lowered: str) -> int:
    """计算指标与问题的文本匹配得分；0 表示不命中。certified 指标在同分时优先。"""
    name = str(metric.name or "").strip()
    if not name:
        return 0
    name_lower = name.lower()
    if name_lower in lowered:
        score = 100
    else:
        tokens = [token for token in re.split(r"[\s_/()-]+", name_lower) if token]
        if tokens and all(token in lowered for token in tokens):
            score = 60
        else:
            aliases = [alias.lower() for alias in _metric_name_aliases(name_lower)]
            if aliases and any(alias and alias in lowered for alias in aliases):
                score = 40
            elif _metric_substring_hit(name_lower, lowered):
                score = 30
            else:
                return 0
    if metric.certification_status == "certified":
        score += 10
    return score


def match_metrics_from_question(
    db: Any,
    question: str,
    datasource: Any,
    dataset_id: int | None = None,
) -> list[dict[str, Any]]:
    """从 Metric 表直接匹配可信指标，certified 优先、返回多候选。

    相比依赖 metrics_prompt 快照的 match_metric_from_question，本函数：
    - 直接读取指标中心的最新数据（不依赖同步时机）；
    - 支持指标名子串/分词全包含/括号别名/中文连续子串四种命中方式，缓解措辞不一致导致的漏命中；
    - certified 指标同分优先，返回按得分降序排列的全部候选，供强约束注入与校验使用；
    - dataset_id 作为软约束而非硬过滤：命中当前数据集加分、未命中且非显式引用时降权（保留兜底候选）；
      当问题显式完整引用指标名/别名时，指标口径优先于数据集作用域，不做降权。
    """
    try:
        from app.models.metric import Metric

        query = db.query(Metric).filter(
            Metric.datasource_id == datasource.id,
            Metric.is_active == 1,
            Metric.status == "published",
            Metric.certification_status != "deprecated",
        )
        metrics = query.all()
    except Exception:
        metrics = []

    lowered = question.lower()
    # 问题显式完整引用某指标（原名或别名）时，指标口径优先，不受数据集作用域限制。
    explicit = any(_metric_question_explicit(metric, lowered) for metric in metrics)

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for metric in metrics:
        score = _metric_match_score(metric, question, lowered)
        if score <= 0:
            continue
        # 数据集相关性：命中当前数据集加分；未命中且非显式引用时降权但不剔除。
        if dataset_id and metric.dataset_id == dataset_id:
            score += 5
        elif dataset_id and not explicit and metric.dataset_id is not None:
            score -= 20
        fixed_filters = _metric_fixed_filters(metric)
        scored.append(
            (
                score,
                1 if metric.certification_status == "certified" else 0,
                {
                    "id": metric.id,
                    "name": metric.name,
                    # formula 为指标完整口径：公式 + 固定筛选（如
                    # COUNT(orders.order_id) WHERE orders.order_status = 'delivered'），
                    # 确保生成 SQL 与校验都遵循指标自带筛选，不漏口径。
                    "formula": metric_caliber_formula(metric),
                    "filters": fixed_filters,
                    "definition": metric.definition,
                    "aggregation": metric.aggregation,
                    "column_name": metric.column_name,
                    "unit": metric.unit,
                    "dimensions": metric.dimensions,
                    "certification_status": metric.certification_status,
                    "quality_status": metric.quality_status,
                    "owner_name": metric.owner_name,
                    "caliber_version": metric.caliber_version,
                    "dataset_id": metric.dataset_id,
                    "match_score": score,
                    "source": "metric_table",
                },
            )
        )
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored]


# ---------------------------------------------------------------------------
# AST 结构级口径校验（sqlglot）
# ---------------------------------------------------------------------------

def _is_zero_literal(node: exp.Expression) -> bool:
    """判断节点是否为数值 0 字面量（如 0、0.0）。"""
    if not isinstance(node, exp.Literal) or node.is_string:
        return False
    try:
        return float(node.this) == 0
    except (TypeError, ValueError):
        return False


def _normalize_ast(node: exp.Expression) -> exp.Expression:
    """规范化表达式 AST（返回副本）：去表限定符、去别名、解包 NULLIF/COALESCE(x,0)。"""
    node = node.copy()
    if isinstance(node, exp.Alias):
        node = node.this
    for column in list(node.find_all(exp.Column)):
        column.set("table", "")
    for nullif in list(node.find_all(exp.Nullif)):
        second = nullif.args.get("expression")
        if second is not None and _is_zero_literal(second):
            nullif.replace(nullif.args.get("this"))
    for coalesce in list(node.find_all(exp.Coalesce)):
        first = coalesce.args.get("this")
        extras = coalesce.expressions
        if first is not None and len(extras) == 1 and _is_zero_literal(extras[0]):
            coalesce.replace(first)
        elif first is not None and not extras:
            coalesce.replace(first)
    return node


def _unwrap_safe_wrappers(node: exp.Expression) -> exp.Expression | None:
    """剥离不影响业务口径的顶层包裹：ROUND、CAST、单参 COALESCE。"""
    for _ in range(3):
        if isinstance(node, exp.Round):
            node = node.args.get("this")
        elif isinstance(node, exp.Cast):
            node = node.this
        elif isinstance(node, exp.Coalesce):
            node = node.args.get("this")
            if node is None:
                break
        else:
            break
    return node


def _ast_sql_text(node: exp.Expression) -> str:
    return re.sub(r"\s+", "", node.sql()).lower()


def _split_and_conditions(expr: exp.Expression) -> list[exp.Expression]:
    conditions: list[exp.Expression] = []
    stack: list[exp.Expression] = [expr]
    while stack:
        node = stack.pop()
        if isinstance(node, exp.And):
            stack.append(node.left)
            stack.append(node.right)
        elif node is not None:
            conditions.append(node)
    return conditions


def sql_uses_metric_formula_ast(sql: str, formula: str | None) -> bool | None:
    """基于 sqlglot AST 的结构级口径校验。

    规则：
    - 公式解析为 `SELECT <expr> FROM __src [WHERE ...]`，提取 select 聚合表达式与 where 条件；
    - SQL 的最终 SELECT 中必须存在一个与公式表达式"结构等价"的投影项
      （可带表限定符/别名，允许 ROUND/CAST/单参 COALESCE 包裹、NULLIF(x,0) 解包）；
    - 公式自带 WHERE 筛选时，SQL 的 WHERE 必须覆盖公式的每个筛选条件
      （结构精确匹配；无法精确匹配时回退宽松校验：字符串字面量与列名子集，兼容 JOIN 等价改写）。

    返回 True/False 表示判定结果；解析失败返回 None，由调用方决定回退策略。
    """
    if not formula:
        return True
    try:
        formula_query = sqlglot.parse_one(f"SELECT {formula} FROM __metric_source")
        sql_ast = sqlglot.parse_one(sql)
    except Exception:
        return None

    try:
        formula_selects = [item for item in formula_query.selects if item is not None]
        formula_where = formula_query.args.get("where")
        sql_selects = [item for item in sql_ast.selects if item is not None]
        if not formula_selects or not sql_selects:
            return None
    except Exception:
        return None

    formula_expr = formula_selects[0]
    formula_normalized = _ast_sql_text(_normalize_ast(formula_expr))
    if not formula_normalized:
        return None

    select_matched = False
    for item in sql_selects:
        normalized = _ast_sql_text(_normalize_ast(item))
        if normalized == formula_normalized:
            select_matched = True
            break
        unwrapped = _unwrap_safe_wrappers(_normalize_ast(item))
        if unwrapped is not None and _ast_sql_text(unwrapped) == formula_normalized:
            select_matched = True
            break
    if not select_matched:
        return False

    if formula_where is None:
        return True

    # 公式自带筛选：要求 SQL 的 WHERE 覆盖公式的每个条件。
    sql_where = sql_ast.args.get("where")
    formula_conditions = _split_and_conditions(formula_where.this)
    sql_conditions = _split_and_conditions(sql_where.this) if sql_where is not None else []
    normalized_sql_conditions = {_ast_sql_text(_normalize_ast(cond)) for cond in sql_conditions}

    strict_matched = True
    for cond in formula_conditions:
        normalized_cond = _ast_sql_text(_normalize_ast(cond))
        if not normalized_cond:
            continue
        if normalized_cond not in normalized_sql_conditions:
            strict_matched = False
            break
    if strict_matched:
        return True

    # 宽松回退：兼容 IN(子查询) 被改写成 JOIN ON 等合法等价改写。
    return _sql_uses_metric_formula_text(sql, formula)


def _sql_uses_metric_formula_text(sql: str, formula: str | None) -> bool:
    """原有文本包含校验，作为 AST 解析失败或结构匹配不适用时的回退。"""
    if not formula:
        return True

    def normalize(value: str) -> str:
        return re.sub(r"\s+", "", value).lower()

    def strip_qualifiers(value: str) -> str:
        return re.sub(r"\b[a-z_][a-z0-9_]*\.", "", value, flags=re.I)

    def contains_expression(target_sql: str, expr: str) -> bool:
        normalized_expr = normalize(expr)
        if normalized_expr in normalize(target_sql):
            return True
        unqualified_expr = normalize(strip_qualifiers(expr))
        unqualified_sql = normalize(strip_qualifiers(target_sql))
        return bool(unqualified_expr and unqualified_expr in unqualified_sql)

    def extract_string_literals(value: str) -> list[str]:
        return [item.lower() for item in re.findall(r"'([^']+)'", value)]

    def extract_column_names(value: str) -> list[str]:
        columns = re.findall(r"\b([a-z_][a-z0-9_]*)\b", strip_qualifiers(value), flags=re.I)
        keywords = {
            "select", "from", "where", "join", "on", "and", "or", "in",
            "sum", "avg", "count", "min", "max", "distinct", "as",
        }
        return [item.lower() for item in columns if item.lower() not in keywords]

    normalized_formula = normalize(formula)
    if normalized_formula in normalize(sql):
        return True

    parts = re.split(r"\bwhere\b", formula, maxsplit=1, flags=re.I)
    formula_head = parts[0].strip()
    formula_tail = parts[1].strip() if len(parts) > 1 else ""

    if formula_head and not contains_expression(sql, formula_head):
        return False

    if not formula_tail:
        return True

    for literal in extract_string_literals(formula_tail):
        # 带引号的精确匹配，避免 "invalid" 误包含 "valid" 这类子串假阳性
        if not re.search(rf"'{re.escape(literal.lower())}'", sql.lower()):
            return False

    sql_columns = set(extract_column_names(sql))
    formula_columns = set(extract_column_names(formula_tail))
    if formula_columns and not formula_columns.issubset(sql_columns):
        return False

    return True


def sql_uses_metric_formula(sql: str, formula: str | None) -> bool:
    """校验生成的 SQL 是否使用了目标指标公式。

    AST 结构级校验优先；解析失败或结构判定不适用时回退到文本包含校验。
    """
    if not formula:
        return True
    ast_result = sql_uses_metric_formula_ast(sql, formula)
    if ast_result is not None:
        return ast_result
    return _sql_uses_metric_formula_text(sql, formula)
