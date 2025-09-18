import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime

from ..config import config


def setup_logging(service_name: str, level: Optional[str] = None) -> logging.Logger:
    """Настройка логирования для сервиса"""

    # Создаем логгер
    logger = logging.getLogger(service_name)

    # Устанавливаем уровень логирования
    log_level = level or config.log_level
    logger.setLevel(getattr(logging, log_level))

    # Удаляем существующие обработчики
    logger.handlers.clear()

    # Создаем обработчик для stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level))

    # Создаем форматтер
    formatter = logging.Formatter(config.log_format)
    handler.setFormatter(formatter)

    # Добавляем обработчик к логгеру
    logger.addHandler(handler)

    return logger


def log_service_event(service_name: str, event: str, message: str, level: str = "INFO"):
    """Логирование событий сервиса"""
    logger = logging.getLogger(service_name)
    log_method = getattr(logger, level.lower())
    log_method(f"[{event}] {message}")


def create_log_entry(
    service: str,
    level: str,
    message: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Создание словаря для записи лога"""
    return {
        "level": level,
        "service": service,
        "message": message,
        "user_id": user_id,
        "session_id": session_id,
        "extra": extra or {},
        "timestamp": datetime.utcnow().isoformat()
    }


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
):
    """Логирование с контекстом"""
    extra_context = extra or {}
    if user_id:
        extra_context["user_id"] = user_id
    if session_id:
        extra_context["session_id"] = session_id

    log_method = getattr(logger, level.lower())
    log_method(message, extra=extra_context)
