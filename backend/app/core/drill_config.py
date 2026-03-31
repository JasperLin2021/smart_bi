from typing import Dict, List

from app.schemas.datasource import DrillConfig, DrillDimension, DrillMetric, DrillPath, SchemaMetadata


DIMENSION_KEYWORDS = {
    "time": ["time", "date", "dt", "hour"],
    "line": ["line"],
    "shift": ["shift"],
    "part": ["part", "model", "sku"],
    "station": ["stn", "station", "op", "process"],
    "ng": ["ngtype", "error", "alarm", "reason", "defect"],
}

METRIC_KEYWORDS = {
    "count": ["count", "qty", "total", "ok", "nok", "ng", "loaded"],
    "rate": ["rate", "oee", "rty", "yield", "ct", "cycletime"],
}

PATH_LABEL_HINTS = {
    "line": "看产线分布",
    "shift": "看班次分布",
    "part": "看料号分布",
    "station": "看工序明细",
    "ng": "看不良类型分布",
    "time": "看时间趋势",
}

EXCLUDED_COLUMNS = {
    "id",
    "mainid",
    "cuser",
    "muser",
    "ctime",
    "mtime",
    "lastupdatetime",
    "hasmakeupdata",
    "stafflevel",
}


def _normalize(value: str) -> str:
    return value.lower().replace("_", "")


def _kind_for_dimension(column_name: str) -> str:
    lowered = _normalize(column_name)
    for kind, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return kind
    return "unknown"


def _metric_aggregation(column_name: str) -> str:
    lowered = _normalize(column_name)
    if any(keyword in lowered for keyword in METRIC_KEYWORDS["rate"]):
        return "avg"
    return "sum"


def _is_dimension(col_type: str, column_name: str) -> bool:
    lowered = _normalize(column_name)
    if lowered in EXCLUDED_COLUMNS or lowered.endswith("id"):
        return False
    if lowered.startswith("h") and lowered[1:].isdigit():
        return False
    if lowered.startswith("r") and lowered[1:].isdigit():
        return False
    kind = _kind_for_dimension(column_name)
    if kind == "unknown":
        return False
    return col_type.upper() in {"VARCHAR", "TEXT", "DATETIME", "DATE", "TIMESTAMP"}


def _is_metric(col_type: str, column_name: str) -> bool:
    lowered = _normalize(column_name)
    if lowered in EXCLUDED_COLUMNS or lowered.endswith("id"):
        return False
    if lowered.startswith("h") and lowered[1:].isdigit():
        return False
    if lowered.startswith("r") and lowered[1:].isdigit():
        return False
    if not any(keyword in lowered for keyword in (METRIC_KEYWORDS["count"] + METRIC_KEYWORDS["rate"])):
        return False
    return col_type.upper() in {"INTEGER", "FLOAT", "NUMERIC", "DECIMAL", "DOUBLE", "REAL"}


def _dimension_label(table_desc: str | None, column_name: str, kind: str) -> str:
    kind_names = {
        "time": "时间",
        "line": "产线",
        "shift": "班次",
        "part": "料号",
        "station": "工位/工序",
        "ng": "异常类型",
        "category": column_name,
    }
    suffix = kind_names.get(kind, column_name)
    return f"{table_desc or '数据'}-{suffix}"


def _metric_label(table_desc: str | None, column_name: str) -> str:
    return f"{table_desc or '数据'}-{column_name}"


def generate_drill_config(schema: SchemaMetadata) -> Dict[str, List[Dict[str, str]]]:
    dimensions: List[DrillDimension] = []
    metrics: List[DrillMetric] = []
    paths: List[DrillPath] = []

    dimensions_by_table: Dict[str, List[DrillDimension]] = {}

    for table in schema.tables:
        table_dimensions: List[DrillDimension] = []
        for col in table.columns:
            if _is_dimension(col.type, col.name):
                kind = _kind_for_dimension(col.name)
                dimension = DrillDimension(
                    id=f"{table.name}.{col.name.lower()}",
                    table=table.name,
                    column=col.name,
                    label=_dimension_label(table.description, col.name, kind),
                    kind=kind,
                )
                dimensions.append(dimension)
                table_dimensions.append(dimension)
            elif _is_metric(col.type, col.name):
                metrics.append(
                    DrillMetric(
                        id=f"{table.name}.{col.name.lower()}",
                        table=table.name,
                        column=col.name,
                        label=_metric_label(table.description, col.name),
                        aggregation=_metric_aggregation(col.name),
                    )
                )
        dimensions_by_table[table.name] = table_dimensions

    for source_table, table_dimensions in dimensions_by_table.items():
        source_candidates = [item for item in table_dimensions if item.kind in {"line", "shift", "part", "station", "time", "category", "ng"}]
        target_candidates = [item for item in table_dimensions if item.kind in {"station", "part", "ng", "time", "shift"}]
        for source in source_candidates:
            for target in target_candidates:
                if source.id == target.id:
                    continue
                if source.kind == target.kind:
                    continue
                path_id = f"{source.id}__{target.id}"
                if any(existing.id == path_id for existing in paths):
                    continue
                paths.append(
                    DrillPath(
                        id=path_id,
                        source_dimension_id=source.id,
                        target_dimension_id=target.id,
                        label=PATH_LABEL_HINTS.get(target.kind, f"看{target.column}明细"),
                        action="group_by",
                    )
                )

    dimension_map = {item.id: item for item in dimensions}
    for relationship in schema.relationships:
        source_dimensions = dimensions_by_table.get(relationship.to_table, [])
        target_dimensions = dimensions_by_table.get(relationship.from_table, [])
        for source in source_dimensions:
            if source.kind not in {"line", "shift", "part", "time", "category"}:
                continue
            for target in target_dimensions:
                if target.kind not in {"station", "ng", "part", "time", "category"}:
                    continue
                path_id = f"{source.id}__{target.id}"
                if any(existing.id == path_id for existing in paths):
                    continue
                paths.append(
                    DrillPath(
                        id=path_id,
                        source_dimension_id=source.id,
                        target_dimension_id=target.id,
                        label=PATH_LABEL_HINTS.get(target.kind, f"看{target.column}明细"),
                        action="group_by",
                    )
                )

    config = DrillConfig(
        dimensions=dimensions,
        metrics=metrics,
        paths=paths,
    )
    return config.model_dump()
