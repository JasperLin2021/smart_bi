"""Base connector interface for FineDataLink-style integrations."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class FieldMeta:
    name: str
    label: str
    type: str          # string | number | date | datetime | boolean
    nullable: bool = True
    example: Any = None


@dataclass
class ObjectMeta:
    name: str
    label: str
    description: str = ""
    supports_incremental: bool = False
    incremental_field: str = ""
    fields: list[FieldMeta] = field(default_factory=list)


class ConnectorError(Exception):
    pass


class BaseConnector(ABC):
    """All connectors must implement this interface."""

    CONNECTOR_TYPE: str = ""
    LABEL: str = ""
    ICON: str = ""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Return (ok, message)."""

    @abstractmethod
    def list_objects(self) -> list[ObjectMeta]:
        """Return metadata for all syncable objects."""

    @abstractmethod
    def fetch_pages(
        self,
        object_name: str,
        filters: dict | None = None,
        incremental_field: str | None = None,
        watermark: str | None = None,
    ) -> Iterator[list[dict]]:
        """Yield pages of records (list of dicts) for the given object."""

    def get_object(self, object_name: str) -> ObjectMeta | None:
        for obj in self.list_objects():
            if obj.name == object_name:
                return obj
        return None


# Registry
_REGISTRY: dict[str, type[BaseConnector]] = {}


def register(cls: type[BaseConnector]) -> type[BaseConnector]:
    _REGISTRY[cls.CONNECTOR_TYPE] = cls
    return cls


def get_connector(connector_type: str, config: dict) -> BaseConnector:
    cls = _REGISTRY.get(connector_type)
    if not cls:
        raise ConnectorError(f"未知连接器类型: {connector_type}")
    return cls(config)


def list_connector_types() -> list[dict]:
    return [
        {"type": cls.CONNECTOR_TYPE, "label": cls.LABEL, "icon": cls.ICON}
        for cls in _REGISTRY.values()
    ]
