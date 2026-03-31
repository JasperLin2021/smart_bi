from pydantic import BaseModel
from typing import Optional


class LlmConfigOut(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    agent_planner_mode: str
    api_key_set: bool


class LlmConfigUpdate(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    agent_planner_mode: str = "llm_only"
    api_key: Optional[str] = None


class LlmConfigTestRequest(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float = 0.3
    api_key: Optional[str] = None
