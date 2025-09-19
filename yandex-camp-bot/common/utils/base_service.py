"""
Базовый класс для микросервисов с общей логикой инициализации и health check
"""

import logging
import time
from typing import Optional, Dict, Any, Callable
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from common.config import config
from common.models import HealthCheckResponse, LogEntry
from common.utils.tracing_middleware import TracingMiddleware, log_error


class BaseService:
    """Базовый класс для микросервисов"""

    def __init__(
        self,
        service_name: str,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[Dict[str, str]] = None
    ):
        self.service_name = service_name
        self.version = version
        self.description = description
        self.dependencies = dependencies or {}
        self.logger = logging.getLogger(self.service_name)

        # Настройка логирования
        self._setup_logging()

        # Создание FastAPI приложения
        self.app = self._create_app()

    def _setup_logging(self):
        """Настройка логирования для сервиса"""
        logging.basicConfig(
            format=config.log_format,
            level=getattr(logging, config.log_level.upper())
        )

    def _create_app(self) -> FastAPI:
        """Создание FastAPI приложения с общими настройками"""
        app = FastAPI(
            title=f"{self.service_name.title()} Service",
            description=self.description,
            version=self.version,
            lifespan=self._lifespan
        )

        # Для monitoring-service не добавляем TracingMiddleware вообще
        if self.service_name != "monitoring-service":
            app.middleware("http")(TracingMiddleware(self.service_name))

        # Добавляем стандартные endpoints
        self._add_standard_routes(app)

        return app

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Общая lifespan функция для всех сервисов"""
        self.logger.info(f"Starting {self.service_name}...")
        await self.on_startup()
        yield
        self.logger.info(f"Shutting down {self.service_name}...")
        await self.on_shutdown()

    async def on_startup(self):
        """Метод для переопределения в дочерних классах"""
        pass

    async def on_shutdown(self):
        """Метод для переопределения в дочерних классах"""
        pass

    def _add_standard_routes(self, app: FastAPI):
        """Добавление стандартных маршрутов"""
        app.get("/health")(self.health_check)
        app.get("/")(self.root)

    def create_health_response(
        self,
        status: str,
        service_status: Optional[str] = None,
        additional_stats: Optional[Dict[str, Any]] = None
    ) -> HealthCheckResponse:
        """Создание стандартного health check ответа"""
        return HealthCheckResponse(
            status=status,
            service=self.service_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            stats={
                "service_status": service_status or status,
                "version": self.version,
                **(additional_stats or {})
            }
        )

    async def health_check(self) -> HealthCheckResponse:
        """Стандартный health check endpoint"""
        try:
            # Проверяем основные зависимости
            dependency_status = await self.check_dependencies()

            if all(status == "available" for status in dependency_status.values()):
                overall_status = "healthy"
            elif any(status == "error" for status in dependency_status.values()):
                overall_status = "unhealthy"
            else:
                overall_status = "degraded"

            return self.create_health_response(
                status=overall_status,
                additional_stats={"dependencies": dependency_status}
            )

        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return self.create_health_response("unhealthy", "error")

    async def check_dependencies(self) -> Dict[str, str]:
        """Проверка зависимостей сервиса"""
        return {dep: "available" for dep in self.dependencies.keys()}

    async def root(self) -> Dict[str, Any]:
        """Стандартный root endpoint с информацией о сервисе"""
        return {
            "service": self.service_name,
            "version": self.version,
            "description": self.description,
            "endpoints": {
                "health": "GET /health",
                "docs": "GET /docs",
                "openapi": "GET /openapi.json"
            }
        }

    def handle_error_response(
        self,
        error: Exception,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Стандартная обработка ошибок"""
        log_error(
            service=self.service_name,
            error_type=type(error).__name__,
            error_message=str(error),
            user_id=user_id,
            session_id=session_id,
            context=context
        )

    def create_error_log_entry(
        self,
        level: str,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> LogEntry:
        """Создание записи лога"""
        return LogEntry(
            level=level,
            service=self.service_name,
            message=message,
            user_id=user_id,
            session_id=session_id,
            extra=extra or {}
        )
