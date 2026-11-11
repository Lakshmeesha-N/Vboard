from typing import Optional

from pydantic import BaseModel


class AgentRequest(BaseModel):
    content: str  # max 10000 chars, may be empty
    languages: Optional[str] = None
    device_id: Optional[str] = None


class AgentResponse(BaseModel):
    text: str  # never empty
    timing_ms: float

