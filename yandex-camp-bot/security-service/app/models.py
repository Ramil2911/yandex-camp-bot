from pydantic import BaseModel, Field
from typing import Optional, Literal
from common.models import (
    LogEntry, HealthCheckResponse,
    SecurityCheckRequest, ModeratorVerdict, SecurityCheckResponse
)


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class SecurityHealthCheckResponse(HealthCheckResponse):
    llm_status: str


#test_ci