from pydantic import BaseModel
from typing import Any, List, Dict, Optional


class QueryAskRequest(BaseModel):
    question: str
    mode: Optional[str] = "business"
    datasource_id: Optional[int] = None
    dataset_id: Optional[int] = None
    drill_context: Optional[Dict[str, Any]] = None
    parent_history_id: Optional[int] = None


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]


class SemanticQueryRequest(BaseModel):
    dataset_id: int
    dimensions: List[str] = []
    metrics: List[str] = []
    filters: List[Dict[str, Any]] = []
    limit: int = 100


class SemanticQueryResponse(BaseModel):
    dataset_id: int
    columns: List[str]
    labels: Dict[str, str]
    rows: List[Dict[str, Any]]
    sql_query: str


class MetricTrustSignal(BaseModel):
    metric_id: int
    metric_name: str
    definition: Optional[str] = None
    formula: Optional[str] = None
    owner_name: Optional[str] = None
    unit: Optional[str] = None
    certification_status: str
    certified_by: Optional[str] = None
    certified_at: Optional[str] = None
    caliber_version: str
    data_updated_at: Optional[str] = None
    quality_status: str
    quality_message: Optional[str] = None


class AgentTraceStep(BaseModel):
    stage: str
    status: str
    message: str
    detail: Optional[Dict[str, Any]] = None


class ChartSpec(BaseModel):
    chart_type: str
    title: Optional[str] = None
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    series_fields: List[str] = []
    layout: str = "single"
    facet_field: Optional[str] = None
    sort_order: str = "none"
    reason: Optional[str] = None


class AgenticRefinementAction(BaseModel):
    label: str
    question: str


class AgenticQueryNotes(BaseModel):
    assumptions: List[str] = []
    risk_flags: List[str] = []
    suggested_refinements: List[AgenticRefinementAction] = []
    confidence: Optional[str] = None


class EmptyDiagnostics(BaseModel):
    reason: str
    checks: List[str] = []
    suggested_actions: List[AgenticRefinementAction] = []


class QueryAskResponse(BaseModel):
    answer: str
    result: QueryResult
    summary: str
    cube_query: Optional[Dict[str, Any]] = None
    sql_query: Optional[str] = None
    llm_model: Optional[str] = None
    history_id: Optional[int] = None
    recommendations: List[str]
    mode: str
    trust_signals: List[MetricTrustSignal] = []
    agent_trace: List[AgentTraceStep] = []
    chart_spec: Optional[ChartSpec] = None
    agent_notes: Optional[AgenticQueryNotes] = None
    empty_diagnostics: Optional[EmptyDiagnostics] = None


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
    mode: str = "business"
    parent_history_id: Optional[int] = None


class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
