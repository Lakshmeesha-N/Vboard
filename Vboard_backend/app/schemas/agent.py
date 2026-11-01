from typing import Optional

from pydantic import BaseModel


class AgentRequest(BaseModel):
    content: str  # max 10000 chars, may be empty
    languages: Optional[str] = None
    device_id: Optional[str] = None


class AgentResponse(BaseModel):
    text: str  # never empty
    used_search: bool
    rounds: int
    note: Optional[str] = None
    timing_ms: float

