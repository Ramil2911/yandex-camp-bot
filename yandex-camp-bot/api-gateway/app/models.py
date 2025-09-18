from pydantic import BaseModel
from typing import Optional, Dict, Any
from common.models import LogEntry, HealthCheckResponse


class TelegramMessage(BaseModel):
    message: str
    user_id: str
    session_id: str
    username: Optional[str] = None


class SecurityCheckRequest(BaseModel):
    message: str
    user_id: str
    session_id: str


class SecurityCheckResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    category: Optional[str] = None


class DialogueRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    context: Optional[Dict[str, Any]] = None


class DialogueResponse(BaseModel):
    response: str
    session_id: str


class RAGSearchRequest(BaseModel):
    query: str
    user_id: str
    session_id: str


class RAGSearchResponse(BaseModel):
    context: str
    documents_found: int
    search_time: float


# LogEntry импортируется из common.models

# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class APIGatewayHealthCheckResponse(HealthCheckResponse):
    dependencies: Dict[str, str]
