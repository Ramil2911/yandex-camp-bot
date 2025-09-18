from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from common.models import LogEntry, HealthCheckResponse


class RAGSearchRequest(BaseModel):
    query: str
    user_id: str
    session_id: str


class DocumentInfo(BaseModel):
    filename: str
    page_count: Optional[int] = None
    content_length: int
    file_type: str


class RAGSearchResponse(BaseModel):
    context: str
    documents_found: int
    search_time: float
    documents_info: Optional[List[DocumentInfo]] = None
    similarity_scores: Optional[List[float]] = None


class RAGSystemInfo(BaseModel):
    enabled: bool
    document_count: int
    collection_name: str
    last_updated: Optional[str] = None
    stats: Dict[str, Any]


class DocumentUploadRequest(BaseModel):
    filename: str
    content: str
    file_type: str


class DocumentUploadResponse(BaseModel):
    success: bool
    message: str
    document_id: Optional[str] = None


# LogEntry импортируется из common.models

# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class RAGHealthCheckResponse(HealthCheckResponse):
    rag_status: str
    vectorstore_status: str
