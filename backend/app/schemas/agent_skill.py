from typing import List, Optional

from pydantic import BaseModel


class AgentSkillOut(BaseModel):
    name: str
    description: str
    source: str
    path: Optional[str] = None
    allowed_actions: List[str] = []


class AgentSkillInstallRequest(BaseModel):
    source: str
