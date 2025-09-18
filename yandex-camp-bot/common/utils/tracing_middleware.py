import time
import uuid
import logging
import traceback
import json
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime

from common.config import config
from common.models.common import TraceEntry, ErrorEntry


class MonitoringClient:
    """Централизованный клиент для отправки данных в monitoring-service"""

    def __init__(self):
        self.monitoring_url = config.monitoring_service_url
        self._client = None

    async def _get_client(self):
        """Получить HTTP клиент (ленивая инициализация)"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0)
        return self._client

    async def send_trace(self, trace: TraceEntry):
        """Отправить трейс в monitoring-service"""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.monitoring_url}/traces",
                json=serialize_for_json(trace.dict())
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send trace: {e}")
            return False

    async def send_error(self, error_entry: ErrorEntry):
        """Отправить ошибку в monitoring-service"""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.monitoring_url}/errors",
                json=serialize_for_json(error_entry.dict())
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send error: {e}")
            return False

    async def send_log(self, level: str, service: str, message: str,
                      user_id: Optional[str] = None, session_id: Optional[str] = None,
                      extra: Optional[Dict[str, Any]] = None):
        """Отправить лог в monitoring-service"""
        try:
            client = await self._get_client()
            log_data = {
                "level": level,
                "service": service,
                "message": message,
                "user_id": user_id,
                "session_id": session_id,
                "extra": extra or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            response = await client.post(
                f"{self.monitoring_url}/logs",
                json=log_data
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send log: {e}")
            return False

    async def create_error(self, service: str, error_type: str, error_message: str,
                          user_id: Optional[str] = None, session_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          stack_trace: Optional[str] = None) -> ErrorEntry:
        """Создать объект ошибки для отправки"""
        # Определяем категорию ошибки на основе типа и сообщения
        category = self._classify_error(error_type, error_message)

        return ErrorEntry(
            trace_id=f"error-{int(time.time())}-{uuid.uuid4().hex[:8]}",
            request_id=f"req-{int(time.time())}",
            service=service,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            context=context or {},
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            category=category
        )

    def _classify_error(self, error_type: str, error_message: str) -> str:
        """Классифицировать ошибку как security или technical"""
        security_keywords = [
            "unauthorized", "forbidden", "authentication", "permission", "access denied",
            "security", "auth", "login", "password", "token", "403", "401",
            "rate limit", "suspicious", "malicious", "attack", "intrusion",
            "sql injection", "xss", "csrf", "brute force"
        ]

        error_text = f"{error_type} {error_message}".lower()

        for keyword in security_keywords:
            if keyword in error_text:
                return "security"

        return "technical"

    async def report_error(self, service: str, error_type: str, error_message: str,
                          user_id: Optional[str] = None, session_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          stack_trace: Optional[str] = None):
        """Удобный метод для отправки ошибки"""
        error_entry = await self.create_error(
            service=service,
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            session_id=session_id,
            context=context,
            stack_trace=stack_trace
        )
        return await self.send_error(error_entry)

    async def close(self):
        """Закрыть HTTP клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Глобальный экземпляр клиента мониторинга
monitoring_client = MonitoringClient()


def log_error(service: str, error_type: str, error_message: str,
              user_id: Optional[str] = None, session_id: Optional[str] = None,
              context: Optional[Dict[str, Any]] = None,
              stack_trace: Optional[str] = None):
    """Синхронная функция для логирования ошибок (создает задачу для асинхронной отправки)"""
    try:
        import asyncio

        async def send_error_async():
            await monitoring_client.report_error(
                service=service,
                error_type=error_type,
                error_message=error_message,
                user_id=user_id,
                session_id=session_id,
                context=context,
                stack_trace=stack_trace
            )

        # Создаем задачу для асинхронной отправки
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если event loop уже запущен, создаем задачу
            loop.create_task(send_error_async())
        else:
            # Иначе запускаем синхронно
            loop.run_until_complete(send_error_async())
    except Exception as e:
        logger.error(f"Failed to create error logging task: {e}")


def log_to_monitoring(level: str, service: str, message: str,
                     user_id: Optional[str] = None, session_id: Optional[str] = None,
                     extra: Optional[Dict[str, Any]] = None):
    """Синхронная функция для отправки логов в мониторинг"""
    try:
        import asyncio

        async def send_log_async():
            await monitoring_client.send_log(
                level=level,
                service=service,
                message=message,
                user_id=user_id,
                session_id=session_id,
                extra=extra
            )

        # Создаем задачу для асинхронной отправки
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если event loop уже запущен, создаем задачу
            loop.create_task(send_log_async())
        else:
            # Иначе запускаем синхронно
            loop.run_until_complete(send_log_async())
    except Exception as e:
        logger.error(f"Failed to create log sending task: {e}")


logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """Сериализатор для JSON с поддержкой datetime"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


class TracingMiddleware:
    """Middleware для автоматического трейсинга запросов"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.monitoring_client = MonitoringClient()

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Генерируем IDs для трейсинга
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        # Создаем более осмысленный request_id с timestamp для лучшей трассируемости
        if "X-Request-Id" not in request.headers:
            timestamp = int(time.time() * 1000000)  # микросекунды для уникальности
            request_id = f"req-{timestamp}-{uuid.uuid4().hex[:8]}"
        else:
            request_id = request.headers["X-Request-Id"]
        span_id = str(uuid.uuid4())

        # Извлекаем контекст пользователя
        user_id = request.headers.get("X-User-Id")
        session_id = request.headers.get("X-Session-Id")

        start_time = time.time()
        start_datetime = datetime.utcnow()

        # Создаем начальный спан
        trace = TraceEntry(
            trace_id=trace_id,
            request_id=request_id,
            span_id=span_id,
            service=self.service_name,
            operation=f"{request.method} {request.url.path}",
            start_time=start_datetime,
            status="running",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "remote_addr": request.client.host if request.client else None
            },
            user_id=user_id,
            session_id=session_id
        )
        await self.monitoring_client.send_trace(trace)

        try:
            # Выполняем запрос
            response = await call_next(request)

            # Завершаем спан успехом
            end_time = time.time()
            end_datetime = datetime.utcnow()
            duration = end_time - start_time

            success_trace = TraceEntry(
                trace_id=trace_id,
                request_id=request_id,
                span_id=span_id,
                service=self.service_name,
                operation=f"{request.method} {request.url.path}",
                start_time=start_datetime,
                end_time=end_datetime,
                duration=duration,
                status="success",
                metadata={
                    "status_code": response.status_code,
                    "response_length": len(response.body) if hasattr(response, 'body') else 0
                },
                user_id=user_id,
                session_id=session_id
            )
            await self.monitoring_client.send_trace(success_trace)

            # Добавляем заголовки для downstream сервисов
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Span-Id"] = span_id

            return response

        except Exception as e:
            # Обрабатываем ошибку
            end_time = time.time()
            end_datetime = datetime.utcnow()
            duration = end_time - start_time

            # Создаем и отправляем ошибку
            error_entry = await self.monitoring_client.create_error(
                service=self.service_name,
                error_type=type(e).__name__,
                error_message=str(e),
                user_id=user_id,
                session_id=session_id,
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": dict(request.headers),
                    "client_ip": request.client.host if request.client else None
                },
                stack_trace=traceback.format_exc()
            )
            await self.monitoring_client.send_error(error_entry)

            # Завершаем спан с ошибкой
            error_trace = TraceEntry(
                trace_id=trace_id,
                request_id=request_id,
                span_id=span_id,
                service=self.service_name,
                operation=f"{request.method} {request.url.path}",
                start_time=start_datetime,
                end_time=end_datetime,
                duration=duration,
                status="error",
                error_message=str(e),
                metadata={
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc()
                },
                user_id=user_id,
                session_id=session_id
            )
            await self.monitoring_client.send_trace(error_trace)

            # Возвращаем ошибку клиенту
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "trace_id": trace_id,
                    "request_id": request_id
                }
            )
