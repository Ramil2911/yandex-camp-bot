from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


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
