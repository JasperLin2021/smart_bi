from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AgentAction(BaseModel):
    type: str
    label: str
    risk: str
    params: Dict[str, Any] = {}


class AgentPlanRequest(BaseModel):
    message: str
    route: str
    datasource_id: Optional[int] = None
    datasource_name: Optional[str] = None


class AgentPlanResponse(BaseModel):
    run_id: int
    skill: Optional[Dict[str, Any]] = None
    reply: str
    reasoning: str
    requires_confirmation: bool
    missing_fields: List[str] = []
    actions: List[AgentAction] = []


class AgentRunCompleteRequest(BaseModel):
    status: str
    execution: List[Dict[str, Any]] = []
