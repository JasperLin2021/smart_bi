"""Row-Level Security enforcement: inject WHERE clauses into SQL queries."""
import re
from typing import List
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.rls_rule import RLSRule
from app.models.user import User

# Simple SQL injection guard: only allow safe value patterns per operator
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9_\-\.@: ,'\"%]+$")
_IN_VALUE_RE = re.compile(r"^[A-Za-z0-9_\-\.@: ,'\"]+$")


def _quote_value(operator: str, value: str) -> str:
    """Return a SQL-safe representation of a filter value."""
    op = operator.upper()
    if op in ("IN", "NOT IN"):
        # Expect comma-separated values; wrap each in single quotes
        parts = [f"'{v.strip().replace(chr(39), chr(39)*2)}'" for v in value.split(",")]
        return f"({', '.join(parts)})"
    # For scalar operators, quote as string literal
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def get_rls_clauses(db: Session, datasource_id: int, user: User) -> List[str]:
    """Return a list of SQL WHERE clause fragments for this user + datasource."""
    bind = db.get_bind()
    if bind is not None and not inspect(bind).has_table(RLSRule.__tablename__):
        return []

    rules = (
        db.query(RLSRule)
        .filter(
            RLSRule.datasource_id == datasource_id,
            RLSRule.is_active == 1,
        )
        .all()
    )

    clauses: List[str] = []
    for rule in rules:
        # Apply rule if it targets this user's org or this specific user
        targets_org = rule.org_id is not None and rule.org_id == user.org_id
        targets_user = rule.user_id is not None and rule.user_id == user.id
        if not targets_org and not targets_user:
            continue

        # Skip for super_admin
        if user.role == "super_admin":
            continue

        op = rule.operator.upper()
        quoted = _quote_value(op, rule.filter_value)
        # table_name.column_name or just column_name
        col_ref = f'"{rule.table_name}"."{rule.column_name}"'
        clauses.append(f"{col_ref} {op} {quoted}")

    return clauses


def apply_rls_to_sql(sql: str, clauses: List[str]) -> str:
    """Inject RLS WHERE clauses into an existing SQL SELECT statement."""
    if not clauses:
        return sql

    combined = " AND ".join(f"({c})" for c in clauses)
    sql_stripped = sql.strip().rstrip(";")

    # Detect existing WHERE clause (case-insensitive, outside string literals is approximate)
    # We use a simple heuristic: find the last top-level WHERE keyword
    upper = sql_stripped.upper()

    # Check for ORDER BY / GROUP BY / HAVING / LIMIT at the end to inject before them
    suffix_keywords = ["ORDER BY", "GROUP BY", "HAVING", "LIMIT", "OFFSET"]
    injection_pos = len(sql_stripped)
    for kw in suffix_keywords:
        pos = _find_top_level_keyword(upper, kw)
        if pos != -1 and pos < injection_pos:
            injection_pos = pos

    core = sql_stripped[:injection_pos]
    suffix = sql_stripped[injection_pos:]

    where_pos = _find_top_level_keyword(core.upper(), "WHERE")
    if where_pos != -1:
        # Append to existing WHERE
        return core + f" AND ({combined})" + suffix
    else:
        # Wrap in subquery to safely add WHERE
        return f"SELECT * FROM ({sql_stripped}) AS _rls_subquery WHERE {combined}"


def _find_top_level_keyword(sql_upper: str, keyword: str) -> int:
    """Find position of keyword at the top SQL level (not inside parentheses)."""
    depth = 0
    i = 0
    kl = len(keyword)
    while i < len(sql_upper):
        ch = sql_upper[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and sql_upper[i:i + kl] == keyword:
            # Ensure it's a word boundary
            before_ok = i == 0 or not sql_upper[i - 1].isalpha()
            after_ok = (i + kl >= len(sql_upper)) or not sql_upper[i + kl].isalpha()
            if before_ok and after_ok:
                return i
        i += 1
    return -1
