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
from common.models.common import TraceEntry, ErrorEntry, ServiceMetrics


class MonitoringClient:
    """Централизованный клиент для отправки данных в monitoring-service"""

    def __init__(self, service_name: str = None):
        # Если это monitoring service, используем localhost для избежания бесконечного цикла
        if service_name == "monitoring-service":
            self.monitoring_url = "http://localhost:8004"
        else:
            self.monitoring_url = config.monitoring_service_url
        self._client = None

    async def _get_client(self):
        """Получить HTTP клиент (ленивая инициализация)"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0)
        return self._client

    async def send_trace(self, trace: TraceEntry):
        """Отправить трейс в monitoring-service (оптимизировано для serverless)"""
        # В serverless режиме отправляем только трейсы с ошибками
        if config.monitoring_config.get("serverless_mode", True):
            if not config.monitoring_config.get("enable_detailed_tracing", False):
                if trace.status != "error" and not config.monitoring_config.get("trace_only_errors", True):
                    return True

        # Полностью отключаем отправку трейсов для monitoring-service
        if hasattr(self, 'service_name') and self.service_name == "monitoring-service":
            return True

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.monitoring_url}/traces",
                json=serialize_for_json(trace.dict())
            )
            return response.status_code == 200
        except Exception as e:
            # В serverless режиме не логируем ошибки отправки трейсов
            if not config.monitoring_config.get("serverless_mode", True):
                logger.error(f"Failed to send trace: {e}")
            return False

    async def send_error(self, error_entry: ErrorEntry):
        """Отправить ошибку в monitoring-service"""
        # Временно отключаем отправку всех ошибок для отладки
        return True

        # Полностью отключаем отправку ошибок для monitoring-service
        if self.service_name == "monitoring-service":
            return True

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
        """Отправить лог в monitoring-service (оптимизировано для serverless)"""
        # В serverless режиме отправляем только ошибки и предупреждения
        if config.monitoring_config.get("serverless_mode", True):
            if level not in ["ERROR", "CRITICAL", "WARNING"]:
                return True

        # Полностью отключаем отправку логов для monitoring-service
        if hasattr(self, 'service_name') and self.service_name == "monitoring-service":
            return True

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
            # В serverless режиме не логируем ошибки отправки логов
            if not config.monitoring_config.get("serverless_mode", True):
                logger.error(f"Failed to send log: {e}")
            return False

    async def create_error(self, service: str, error_type: str, error_message: str,
                          user_id: Optional[str] = None, session_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          stack_trace: Optional[str] = None,
                          trace_id: Optional[str] = None,
                          request_id: Optional[str] = None) -> ErrorEntry:
        """Создать объект ошибки для отправки"""
        # Определяем категорию ошибки на основе типа и сообщения
        category = self._classify_error(error_type, error_message)

        # Используем переданные trace_id и request_id, или создаем новые
        if not trace_id:
            trace_id = f"error-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        if not request_id:
            request_id = f"req-{int(time.time())}"

        return ErrorEntry(
            trace_id=trace_id,
            request_id=request_id,
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
            "security", "auth", "unauthorized", "forbidden", "access", "permission",
            "injection", "xss", "csrf", "sql", "malicious", "attack", "breach",
            "hack", "exploit", "vulnerability", "suspicious", "blocked", "denied"
        ]
        
        error_text = f"{error_type} {error_message}".lower()
        if any(keyword in error_text for keyword in security_keywords):
            return "security"
        return "technical"

    async def report_error(self, service: str, error_type: str, error_message: str,
                          user_id: Optional[str] = None, session_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          stack_trace: Optional[str] = None,
                          trace_id: Optional[str] = None,
                          request_id: Optional[str] = None):
        """Удобный метод для отправки ошибки"""
        error_entry = await self.create_error(
            service=service,
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            session_id=session_id,
            context=context,
            stack_trace=stack_trace,
            trace_id=trace_id,
            request_id=request_id
        )
        return await self.send_error(error_entry)

    async def close(self):
        """Закрыть HTTP клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Глобальный экземпляр клиента мониторинга
monitoring_client = MonitoringClient()


class ServiceTimingTracker:
    """Класс для отслеживания времени обработки запросов в сервисах"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._timings = {}  # request_id -> timing_data

    def start_request(self, request_id: str, user_id: str = None, session_id: str = None, expected_services: list = None):
        """Начать отслеживание времени для нового запроса"""
        if request_id not in self._timings:
            self._timings[request_id] = {
                "user_id": user_id,
                "session_id": session_id,
                "start_time": time.time(),
                "services": {},
                "expected_services": expected_services or ["security-service", "rag-service", "dialogue-service"],
                "status": "running",
                "completed_services": set()
            }

    def start_service_timing(self, request_id: str, service_name: str):
        """Начать отслеживание времени для конкретного сервиса"""
        if request_id in self._timings:
            if service_name not in self._timings[request_id]["services"]:
                self._timings[request_id]["services"][service_name] = {
                    "start_time": time.time(),
                    "end_time": None,
                    "duration": None
                }

    def end_service_timing(self, request_id: str, service_name: str, status: str = "success"):
        """Закончить отслеживание времени для конкретного сервиса"""
        if request_id in self._timings:
            if service_name in self._timings[request_id]["services"]:
                service_data = self._timings[request_id]["services"][service_name]
                service_data["end_time"] = time.time()
                service_data["duration"] = service_data["end_time"] - service_data["start_time"]

                # Добавляем в список завершенных сервисов
                self._timings[request_id]["completed_services"].add(service_name)

                # Проверяем, все ли ожидаемые сервисы завершили обработку
                expected_services = set(self._timings[request_id]["expected_services"])
                completed_services = self._timings[request_id]["completed_services"]

                if expected_services.issubset(completed_services):
                    # Все сервисы завершили работу
                    self._timings[request_id]["status"] = status
                    self._timings[request_id]["end_time"] = time.time()
                    self._timings[request_id]["total_duration"] = (
                        self._timings[request_id]["end_time"] - self._timings[request_id]["start_time"]
                    )

                    # Отправляем метрики сервисным аккаунтам
                    self._send_service_metrics(request_id)

    def _send_service_metrics(self, request_id: str):
        """Отправить метрики времени сервисным аккаунтам"""
        timing_data = self._timings.get(request_id)
        if not timing_data or timing_data["status"] == "running":
            return

        services_timing = {}
        for service_name, service_data in timing_data["services"].items():
            if service_data["duration"] is not None:
                services_timing[service_name] = service_data["duration"]

        metrics = ServiceMetrics(
            request_id=request_id,
            user_id=timing_data["user_id"],
            session_id=timing_data["session_id"],
            timestamp=datetime.utcnow(),
            services_timing=services_timing,
            total_time=timing_data["total_duration"],
            status=timing_data["status"]
        )

        # Отправляем метрики в API Gateway для рассылки сервисным аккаунтам
        self._send_to_api_gateway_sync(metrics)

        # Очищаем данные после отправки
        del self._timings[request_id]

    def _send_to_api_gateway_sync(self, metrics: ServiceMetrics):
        """Отправить метрики в API Gateway (синхронно)"""
        try:
            import requests
            response = requests.post(
                f"{config.api_gateway_url or 'http://api-gateway:8000'}/service-metrics",
                json=serialize_for_json(metrics.dict()),
                timeout=5.0
            )
            if response.status_code != 200:
                logger.error(f"Failed to send metrics, status: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send service metrics: {e}")

    async def _send_to_api_gateway(self, metrics: ServiceMetrics):
        """Отправить метрики в API Gateway (асинхронно)"""
        try:
            client = httpx.AsyncClient(timeout=5.0)
            response = await client.post(
                f"{config.api_gateway_url or 'http://api-gateway:8000'}/service-metrics",
                json=serialize_for_json(metrics.dict())
            )
            await client.aclose()
        except Exception as e:
            logger.error(f"Failed to send service metrics: {e}")


# Глобальный трекер времени
service_timing_tracker = ServiceTimingTracker("global")


def log_error(service: str, error_type: str, error_message: str,
              user_id: Optional[str] = None, session_id: Optional[str] = None,
              context: Optional[Dict[str, Any]] = None,
              stack_trace: Optional[str] = None):
    """Синхронная функция для логирования ошибок"""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        
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
        
        if loop.is_running():
            # Если цикл уже запущен, создаем задачу
            asyncio.create_task(send_error_async())
        else:
            # Иначе запускаем синхронно
            loop.run_until_complete(send_error_async())
    except Exception as e:
        logger.error(f"Failed to create error sending task: {e}")


def log_info(service: str, message: str, user_id: Optional[str] = None, 
             session_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None):
    """Синхронная функция для логирования информации"""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        
        async def send_log_async():
            await monitoring_client.send_log(
                level="INFO",
                service=service,
                message=message,
                user_id=user_id,
                session_id=session_id,
                extra=extra
            )
        
        if loop.is_running():
            # Если цикл уже запущен, создаем задачу
            asyncio.create_task(send_log_async())
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
        self.monitoring_client = MonitoringClient(service_name)
        self.timing_tracker = ServiceTimingTracker(service_name)

    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Для monitoring-service отключаем трейсинг полностью, чтобы избежать бесконечного цикла
        if self.service_name == "monitoring-service":
            return await call_next(request)
            
        # В serverless режиме пропускаем трейсинг health checks
        if (config.monitoring_config.get("serverless_mode", True) and 
            config.monitoring_config.get("disable_monitoring_for_health", True) and 
            request.url.path in ["/health", "/", "/docs", "/openapi.json"]):
            return await call_next(request)
            
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        # Создаем более осмысленный request_id с timestamp для лучшей трассируемости
        if "X-Request-Id" not in request.headers:
            request_id = f"req-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        else:
            request_id = request.headers["X-Request-Id"]
        span_id = str(uuid.uuid4())

        # Извлекаем контекст пользователя
        user_id = request.headers.get("X-User-Id")
        session_id = request.headers.get("X-Session-Id")

        # Начинаем отслеживание времени для запроса
        self.timing_tracker.start_request(request_id, user_id, session_id)
        self.timing_tracker.start_service_timing(request_id, self.service_name)

        start_time = time.time()
        start_datetime = datetime.utcnow()

        # Отправляем трейс только если это не monitoring-service (избегаем бесконечного цикла)
        should_trace = (self.service_name != "monitoring-service" and 
                       config.monitoring_config.get("enable_detailed_tracing", False))

        if should_trace:
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

            # Завершаем отслеживание времени для этого сервиса
            self.timing_tracker.end_service_timing(request_id, self.service_name, "success")

            if should_trace:
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
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                        "user_agent": request.headers.get("user-agent"),
                        "remote_addr": request.client.host if request.client else None,
                        "status_code": response.status_code,
                        "response_headers": dict(response.headers)
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                await self.monitoring_client.send_trace(success_trace)

            return response

        except Exception as e:
            # Логируем ошибку
            end_time = time.time()
            end_datetime = datetime.utcnow()
            duration = end_time - start_time

            # Завершаем отслеживание времени для этого сервиса с ошибкой
            self.timing_tracker.end_service_timing(request_id, self.service_name, "error")

            if should_trace:
                # Создаем запись об ошибке с тем же trace_id и request_id
                error_entry = await self.monitoring_client.create_error(
                    service=self.service_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    user_id=user_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    request_id=request_id,
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
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                        "user_agent": request.headers.get("user-agent"),
                        "remote_addr": request.client.host if request.client else None,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e)
                    },
                    user_id=user_id,
                    session_id=session_id
                )
                await self.monitoring_client.send_trace(error_trace)

            # Возвращаем ошибку как JSON ответ
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": str(e),
                    "trace_id": trace_id,
                    "request_id": request_id
                }
            )

    async def close(self):
        """Закрыть клиент мониторинга"""
        await self.monitoring_client.close()