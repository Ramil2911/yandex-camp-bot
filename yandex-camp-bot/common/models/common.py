from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from enum import Enum


class LogEntry(BaseModel):
    """Общая модель для лог-записей"""
    level: str
    service: str
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class TraceEntry(BaseModel):
    """Модель для трейсов запросов"""
    trace_id: str
    request_id: str
    span_id: str
    service: str
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    status: str  # "success", "error", "running"
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ErrorEntry(BaseModel):
    """Модель для детальной информации об ошибках"""
    trace_id: str
    request_id: str
    service: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    category: str = "technical"  # "security" или "technical"


class HealthCheckResponse(BaseModel):
    """Общая модель для проверки здоровья сервисов"""
    status: str
    service: str
    timestamp: str
    stats: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Общая модель для ошибок"""
    error: str
    detail: Optional[str] = None
    service: str


class ServiceInfo(BaseModel):
    """Общая модель для информации о сервисе"""
    name: str
    version: str
    description: str
    endpoints: Dict[str, str]
    dependencies: Optional[Dict[str, str]] = None


# RAG (Retrieval-Augmented Generation) модели
class RAGSearchRequest(BaseModel):
    """Запрос на поиск в RAG системе"""
    query: str
    user_id: str
    session_id: str


class DocumentInfo(BaseModel):
    """Информация о документе"""
    filename: str
    page_count: Optional[int] = None
    content_length: int
    file_type: str


class QueryAnalysisResult(BaseModel):
    """Результат анализа запроса LLM"""
    rag_required: bool
    reasoning: Optional[str] = None
    rephrased_queries: List[str] = []


class RAGSearchResponse(BaseModel):
    """Ответ RAG системы"""
    context: str
    documents_found: int
    search_time: float
    documents_info: Optional[List[DocumentInfo]] = None
    similarity_scores: Optional[List[float]] = None
    analysis_result: Optional[QueryAnalysisResult] = None  # Результат анализа запроса
    queries_used: Optional[List[str]] = None  # Запросы, по которым выполнялся поиск
    error: Optional[str] = None


class RAGSystemInfo(BaseModel):
    """Информация о состоянии RAG системы"""
    status: str
    document_count: int
    last_indexing_time: Optional[str] = None
    stats: Dict[str, Any]
    error: Optional[str] = None


class DocumentUploadRequest(BaseModel):
    """Запрос на загрузку документа"""
    filename: str
    content: str
    file_type: str


class DocumentUploadResponse(BaseModel):
    """Ответ на загрузку документа"""
    success: bool
    message: str
    document_id: Optional[str] = None


# Модели безопасности
class SecurityCheckRequest(BaseModel):
    """Запрос на проверку безопасности"""
    message: str
    user_id: str
    session_id: str


class ModeratorVerdict(BaseModel):
    """Вердикт модератора"""
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
    """Ответ на проверку безопасности"""
    allowed: bool
    reason: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0
    processing_time: float = 0.0


# Модели Telegram
class TelegramMessage(BaseModel):
    """Модель сообщения Telegram"""
    message: str
    user_id: str
    session_id: str
    username: Optional[str] = None


# Модели диалога
class DialogueRequest(BaseModel):
    """Запрос на обработку диалога"""
    message: str
    user_id: str
    session_id: str
    context: Optional[Dict[str, Any]] = None


class DialogueResponse(BaseModel):
    """Ответ на обработку диалога"""
    response: str
    session_id: str
    processing_time: float
    tokens_used: Optional[int] = None
    context_used: bool = False


class MemoryEntry(BaseModel):
    """Запись памяти"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float


class SessionMemory(BaseModel):
    """Память сессии"""
    session_id: str
    messages: List[MemoryEntry]
    created_at: float
    last_accessed: float
    user_id: str


class ClearMemoryRequest(BaseModel):
    """Запрос на очистку памяти"""
    session_id: str
    user_id: str


class ClearMemoryResponse(BaseModel):
    """Ответ на очистку памяти"""
    success: bool
    message: str
    messages_cleared: int


class DialogueStats(BaseModel):
    """Статистика диалогов"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    active_sessions: int
    total_tokens_used: int
