from pydantic import BaseModel, Field
from typing import Optional, Literal
from common.models import LogEntry, HealthCheckResponse


class SecurityCheckRequest(BaseModel):
    message: str
    user_id: str
    session_id: str


class ModeratorVerdict(BaseModel):
    decision: Literal["allow", "flag", "block"] = Field(
        description="Final moderation decision for the user prompt"
    )
    categories: Literal[None, 'malware', 'hate', 'self-harm', 'sexual', 'pii', 'jailbreak', 'etc'] = Field(
        default=None,
        description="Matched policy categories. Must be None if the decision is 'allow'."
    )
    reason: str = Field(
        description="Very short and concise justification for the decision. Leave empty if the decision is 'allow'."
    )


class SecurityCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0
    processing_time: float = 0.0


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class SecurityHealthCheckResponse(HealthCheckResponse):
    llm_status: str
