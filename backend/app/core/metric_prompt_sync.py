from sqlalchemy.orm import Session

from app.models.datasource import DataSource
from app.models.metric import Metric


def _calculation_filter_text(filters: object) -> str:
    if not isinstance(filters, list):
        return ""
    parts: list[str] = []
    for item in filters:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        operator = str(item.get("operator") or "=").strip()
        value = str(item.get("value") or "").strip()
        if field and operator:
            parts.append(f"{field} {operator} {value}".strip())
    return "；".join(parts)


def build_metrics_prompt(metrics: list[dict]) -> str | None:
    if not metrics:
        return None

    lines = ["可用指标："]
    for metric in metrics:
        name = metric.get("name") or "未命名指标"
        description = (metric.get("description") or "").strip()
        definition = (metric.get("definition") or "").strip()
        formula = (metric.get("formula") or "").strip()
        unit = (metric.get("unit") or "").strip()
        aggregation = (metric.get("aggregation") or "").strip()
        calculation_config = metric.get("calculation_config") or {}
        if not isinstance(calculation_config, dict):
            calculation_config = {}

        parts = [f"- {name}:"]
        if description:
            parts.append(description)
        elif definition:
            parts.append(definition)
        if unit:
            parts.append(f"单位：{unit}")
        if aggregation:
            parts.append(f"聚合：{aggregation}")
        if calculation_config.get("statistical_window"):
            parts.append(f"统计周期：{calculation_config['statistical_window']}")
        if calculation_config.get("time_grain"):
            parts.append(f"时间粒度：{calculation_config['time_grain']}")
        if calculation_config.get("time_field"):
            parts.append(f"时间字段：{calculation_config['time_field']}")
        if calculation_config.get("numerator_expression"):
            parts.append(f"分子：{calculation_config['numerator_expression']}")
        if calculation_config.get("denominator_expression"):
            parts.append(f"分母：{calculation_config['denominator_expression']}")
        filter_text = _calculation_filter_text(calculation_config.get("filters"))
        if filter_text:
            parts.append(f"过滤条件：{filter_text}")
        if calculation_config.get("null_handling"):
            parts.append(f"空值处理：{calculation_config['null_handling']}")
        if calculation_config.get("dedup_key"):
            parts.append(f"去重键：{calculation_config['dedup_key']}")
        if calculation_config.get("denominator_zero_policy"):
            parts.append(f"分母为零：{calculation_config['denominator_zero_policy']}")
        if calculation_config.get("validation_rule"):
            parts.append(f"校验规则：{calculation_config['validation_rule']}")
        if formula:
            parts.append(f"计算公式：{formula}")
        lines.append(" ".join(parts))

    return "\n".join(lines)


def sync_datasource_metrics_prompt(db: Session, datasource_id: int) -> None:
    datasource = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not datasource:
        return

    metrics = (
        db.query(Metric)
        .filter(
            Metric.datasource_id == datasource_id,
            Metric.is_active == 1,
            Metric.status == "published",
            Metric.certification_status != "deprecated",
        )
        .order_by(Metric.updated_at.desc(), Metric.id.desc())
        .all()
    )
    datasource.metrics_prompt = build_metrics_prompt(
        [
            {
                "name": item.name,
                "description": item.description,
                "definition": item.definition,
                "formula": item.formula,
                "calculation_config": item.calculation_config,
                "unit": item.unit,
                "aggregation": item.aggregation,
            }
            for item in metrics
        ]
    )
