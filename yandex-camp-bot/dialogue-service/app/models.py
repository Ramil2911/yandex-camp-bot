from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from common.models import LogEntry, HealthCheckResponse


class DialogueRequest(BaseModel):
    message: str
    user_id: str
    session_id: str
    context: Optional[Dict[str, Any]] = None


class DialogueResponse(BaseModel):
    response: str
    session_id: str
    processing_time: float
    tokens_used: Optional[int] = None
    context_used: bool = False


class MemoryEntry(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: float


class SessionMemory(BaseModel):
    session_id: str
    messages: List[MemoryEntry]
    created_at: float
    last_accessed: float
    user_id: str


class ClearMemoryRequest(BaseModel):
    session_id: str
    user_id: str


class ClearMemoryResponse(BaseModel):
    success: bool
    message: str
    messages_cleared: int


# LogEntry импортируется из common.models


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class DialogueHealthCheckResponse(HealthCheckResponse):
    llm_status: str
    memory_sessions: int


class DialogueStats(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    active_sessions: int
    total_tokens_used: int
