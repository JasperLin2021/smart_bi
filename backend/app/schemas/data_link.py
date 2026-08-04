from pydantic import BaseModel, field_serializer
from typing import Optional, List, Any
from datetime import datetime

# Keys in a connector config whose values must never be returned to clients.
_SECRET_KEY_HINTS = ("secret", "password", "token", "key", "credential")


def _mask_secrets(config: Optional[dict]) -> Optional[dict]:
    if not config:
        return config
    masked = {}
    for key, value in config.items():
        if isinstance(value, str) and value and any(hint in key.lower() for hint in _SECRET_KEY_HINTS):
            masked[key] = "********"
        else:
            masked[key] = value
    return masked


class DataLinkCreate(BaseModel):
    name: str
    connector_type: str
    config_json: Optional[dict] = None


class DataLinkUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[dict] = None
    status: Optional[str] = None


class DataLinkOut(BaseModel):
    id: int
    name: str
    connector_type: str
    config_json: Optional[dict] = None
    status: str
    last_test_at: Optional[datetime] = None
    last_test_message: Optional[str] = None
    org_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer("config_json")
    def _serialize_config(self, value: Optional[dict]) -> Optional[dict]:
        return _mask_secrets(value)


class FieldMapping(BaseModel):
    src: str
    dst: str
    type: str = "string"


class DataLinkTaskCreate(BaseModel):
    link_id: int
    name: str
    source_object: str
    target_datasource_id: Optional[int] = None
    target_table: Optional[str] = None
    sync_mode: str = "full"
    incremental_field: Optional[str] = None
    field_mapping_json: Optional[List[dict]] = None
    filter_json: Optional[dict] = None
    cron_expression: str = "0 2 * * *"
    is_active: bool = True


class DataLinkTaskUpdate(BaseModel):
    name: Optional[str] = None
    target_datasource_id: Optional[int] = None
    target_table: Optional[str] = None
    sync_mode: Optional[str] = None
    incremental_field: Optional[str] = None
    field_mapping_json: Optional[List[dict]] = None
    filter_json: Optional[dict] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None


class DataLinkTaskOut(BaseModel):
    id: int
    link_id: int
    name: str
    source_object: str
    target_datasource_id: Optional[int] = None
    target_table: Optional[str] = None
    sync_mode: str
    incremental_field: Optional[str] = None
    incremental_watermark: Optional[str] = None
    field_mapping_json: Optional[List[dict]] = None
    filter_json: Optional[dict] = None
    cron_expression: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_records: Optional[int] = None
    org_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DataLinkLogOut(BaseModel):
    id: int
    task_id: int
    link_id: int
    status: str
    records_read: int = 0
    records_written: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True
