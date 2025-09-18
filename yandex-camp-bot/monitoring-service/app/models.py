from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from common.models import LogEntry, HealthCheckResponse, TraceEntry, ErrorEntry


# LogEntry импортируется из common.models

class LogEntryCreate(LogEntry):
    timestamp: datetime = datetime.utcnow()


class LogEntryResponse(LogEntry):
    id: int
    created_at: datetime


class MetricsEntry(BaseModel):
    service: str
    metric_name: str
    value: float
    tags: Optional[Dict[str, str]] = None
    timestamp: Optional[datetime] = None


class MetricsEntryCreate(MetricsEntry):
    timestamp: datetime = datetime.utcnow()


class MetricsEntryResponse(MetricsEntry):
    id: int
    created_at: datetime


class ServiceHealth(BaseModel):
    service_name: str
    status: str  # "healthy", "degraded", "unhealthy"
    last_check: datetime
    response_time: Optional[float] = None
    error_message: Optional[str] = None


class SystemStats(BaseModel):
    total_logs: int
    logs_today: int
    active_services: int
    error_rate_24h: float
    avg_response_time: float


class LogQuery(BaseModel):
    service: Optional[str] = None
    level: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


# HealthCheckResponse наследуется от общего и расширяется специфичными полями
class MonitoringHealthCheckResponse(HealthCheckResponse):
    database_status: str


class BulkLogResponse(BaseModel):
    inserted: int
    errors: int
    processing_time: float


class TraceEntryCreate(TraceEntry):
    pass


class TraceEntryResponse(TraceEntry):
    id: int
    created_at: datetime


class ErrorEntryCreate(ErrorEntry):
    pass


class ErrorEntryResponse(BaseModel):
    """Response model for error entries"""
    id: int
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
    category: str
    created_at: datetime


class TraceQuery(BaseModel):
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    service: Optional[str] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class ErrorQuery(BaseModel):
    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    service: Optional[str] = None
    error_type: Optional[str] = None
    category: Optional[str] = None  # "security" или "technical"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class FullTraceResponse(BaseModel):
    """Полный трейс запроса через все сервисы"""
    request_id: str
    trace_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None
    status: str
    services_path: List[Dict[str, Any]] = []  # Путь через сервисы
    errors: List[Dict[str, Any]] = []  # Все ошибки в трейсе
