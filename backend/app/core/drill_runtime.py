from typing import Any, Dict, List


def _normalize(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "")


def _short_label(value: str) -> str:
    return value.split("-")[-1] if "-" in value else value


def build_drill_actions(
    config: Dict[str, Any] | None,
    columns: List[str],
    row: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not config:
        return []

    dimensions = {item["id"]: item for item in config.get("dimensions", []) if item.get("enabled")}
    paths = [item for item in config.get("paths", []) if item.get("enabled")]
    if not dimensions or not paths:
        return []

    column_map = {_normalize(col): col for col in columns}
    actions: List[Dict[str, Any]] = []
    seen_targets = set()

    for path in paths:
        source = dimensions.get(path["source_dimension_id"])
        target = dimensions.get(path["target_dimension_id"])
        if not source or not target:
            continue

        source_column = column_map.get(_normalize(source["column"]))
        if not source_column or source_column not in row:
            continue

        source_value = row.get(source_column)
        if source_value in (None, "", "NULL"):
            continue

        short_source_label = _short_label(source["label"])
        short_target_label = _short_label(target["label"])
        dedupe_key = (source["id"], short_target_label, path["label"])
        if dedupe_key in seen_targets:
            continue
        seen_targets.add(dedupe_key)

        actions.append(
            {
                "id": path["id"],
                "label": path["label"],
                "action": path.get("action", "group_by"),
                "source_dimension_id": source["id"],
                "source_dimension_label": short_source_label,
                "source_column": source["column"],
                "source_value": source_value,
                "target_dimension_id": target["id"],
                "target_dimension_label": short_target_label,
                "target_column": target["column"],
                "question": f"只看{short_source_label}为 {source_value} 的数据，按{short_target_label}继续分析。",
            }
        )

    return actions[:6]
