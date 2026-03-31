from pydantic import BaseModel
from typing import Any, List, Dict, Optional


class QueryAskRequest(BaseModel):
    question: str
    mode: Optional[str] = "text2sql"
    datasource_id: Optional[int] = None
    drill_context: Optional[Dict[str, Any]] = None
    parent_history_id: Optional[int] = None


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]


class QueryAskResponse(BaseModel):
    answer: str
    result: QueryResult
    summary: str
    cube_query: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    history_id: Optional[int] = None
    recommendations: List[str]
    mode: str


class DrillAction(BaseModel):
    id: str
    label: str
    action: str
    source_dimension_id: str
    source_dimension_label: str
    source_column: str
    source_value: Any
    target_dimension_id: str
    target_dimension_label: str
    target_column: str
    question: str


class DrillPreviewRequest(BaseModel):
    datasource_id: int
    question: str
    sql_query: str
    selected_column: str
    columns: List[str]
    row: Dict[str, Any]


class DrillPreviewResponse(BaseModel):
    actions: List[DrillAction]
    detail_action: Optional[DrillAction] = None


class HistoryItem(BaseModel):
    id: int
    question: str
    created_at: str
    favorite: bool
    parent_history_id: Optional[int] = None


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
