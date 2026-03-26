from pydantic import BaseModel
from typing import Any, List, Dict, Optional


class QueryAskRequest(BaseModel):
    question: str
    mode: Optional[str] = "text2sql"
    datasource_id: Optional[int] = None


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]


class QueryAskResponse(BaseModel):
    answer: str
    result: QueryResult
    summary: str
    cube_query: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    recommendations: List[str]
    mode: str


class HistoryItem(BaseModel):
    id: int
    question: str
    created_at: str
    favorite: bool


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
