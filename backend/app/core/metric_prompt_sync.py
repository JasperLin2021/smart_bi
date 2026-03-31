from sqlalchemy.orm import Session

from app.models.datasource import DataSource
from app.models.metric import Metric


def build_metrics_prompt(metrics: list[dict]) -> str | None:
    if not metrics:
        return None

    lines = ["可用指标："]
    for metric in metrics:
        name = metric.get("name") or "未命名指标"
        description = (metric.get("description") or "").strip()
        definition = (metric.get("definition") or "").strip()
        formula = (metric.get("formula") or "").strip()

        parts = [f"- {name}:"]
        if description:
            parts.append(description)
        elif definition:
            parts.append(definition)
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
        .filter(Metric.datasource_id == datasource_id, Metric.is_active == 1)
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
            }
            for item in metrics
        ]
    )
