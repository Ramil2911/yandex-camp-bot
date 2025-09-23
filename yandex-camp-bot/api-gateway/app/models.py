from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from common.models import (
    LogEntry, HealthCheckResponse,
    TelegramMessage, SecurityCheckRequest, SecurityCheckResponse,
    DialogueRequest, DialogueResponse, RAGSearchRequest, RAGSearchResponse,
    ServiceAccount, ServiceMetrics
)


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class APIGatewayHealthCheckResponse(HealthCheckResponse):
    dependencies: Dict[str, str]
