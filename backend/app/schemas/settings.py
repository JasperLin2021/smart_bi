from pydantic import BaseModel
from typing import Optional


class LlmConfigOut(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    api_key_set: bool


class LlmConfigUpdate(BaseModel):
    provider: str
    base_url: str
    model: str
    temperature: float
    api_key: Optional[str] = None
