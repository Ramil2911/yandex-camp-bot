from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from common.models import (
    LogEntry, HealthCheckResponse,
    DialogueRequest, DialogueResponse, MemoryEntry,
    SessionMemory, ClearMemoryRequest, ClearMemoryResponse,
    DialogueStats
)


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class DialogueHealthCheckResponse(HealthCheckResponse):
    llm_status: str
    memory_sessions: int
