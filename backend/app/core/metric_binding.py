import re


def _parse_metrics_prompt(metrics_prompt: str | None) -> list[dict]:
    if not metrics_prompt:
        return []

    metrics: list[dict] = []
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


def match_metric_from_question(question: str, datasource) -> dict | None:
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


def sql_uses_metric_formula(sql: str, formula: str | None) -> bool:
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
        if literal not in sql.lower():
            return False

    sql_columns = set(extract_column_names(sql))
    formula_columns = set(extract_column_names(formula_tail))
    if formula_columns and not formula_columns.issubset(sql_columns):
        return False

    return True
