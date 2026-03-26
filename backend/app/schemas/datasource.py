from pydantic import BaseModel
from typing import Optional, List, Any


class ColumnSchema(BaseModel):
    name: str
    type: str
    description: Optional[str] = None


class TableSchema(BaseModel):
    name: str
    description: Optional[str] = None
    columns: List[ColumnSchema] = []


class RelationshipSchema(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class SchemaMetadata(BaseModel):
    tables: List[TableSchema] = []
    relationships: List[RelationshipSchema] = []


class DataSourceCreate(BaseModel):
    name: str
    slug: str
    database_url: str
    source_type: Optional[str] = "database"  # "database" | "excel"
    metadata_prompt: str
    schema_metadata: Optional[SchemaMetadata] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None
    org_id: Optional[int] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    database_url: Optional[str] = None
    source_type: Optional[str] = None
    metadata_prompt: Optional[str] = None
    schema_metadata: Optional[SchemaMetadata] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None
    is_active: Optional[int] = None
    org_id: Optional[int] = None


class DataSourceOut(BaseModel):
    id: int
    name: str
    slug: str
    source_type: str
    metadata_prompt: str
    schema_metadata: Optional[SchemaMetadata] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None
    is_active: int
    org_id: Optional[int] = None

    class Config:
        from_attributes = True


class DataSourceListItem(BaseModel):
    id: int
    name: str
    slug: str
    is_active: int
    org_id: Optional[int] = None
    source_type: Optional[str] = None

    class Config:
        from_attributes = True
