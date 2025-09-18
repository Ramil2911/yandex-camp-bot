from pydantic import BaseModel
from typing import Optional, Dict, Any


class LogEntry(BaseModel):
    """Общая модель для лог-записей"""
    level: str
    service: str
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


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
