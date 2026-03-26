from pydantic import BaseModel
from typing import Optional, List


class DataSourceCreate(BaseModel):
    name: str
    slug: str
    database_url: str
    metadata_prompt: str
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    database_url: Optional[str] = None
    metadata_prompt: Optional[str] = None
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None
    is_active: Optional[int] = None


class DataSourceOut(BaseModel):
    id: int
    name: str
    slug: str
    metadata_prompt: str
    metrics_prompt: Optional[str] = None
    text2sql_prompt: Optional[str] = None
    recommend_questions: Optional[List[str]] = None
    is_active: int

    class Config:
        from_attributes = True


class DataSourceListItem(BaseModel):
    id: int
    name: str
    slug: str
    is_active: int

    class Config:
        from_attributes = True
