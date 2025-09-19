from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from common.models import (
    LogEntry, HealthCheckResponse,
    RAGSearchRequest, DocumentInfo, QueryAnalysisResult,
    RAGSearchResponse, RAGSystemInfo,
    DocumentUploadRequest, DocumentUploadResponse
)


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class RAGHealthCheckResponse(HealthCheckResponse):
    rag_status: str
    vectorstore_status: str
