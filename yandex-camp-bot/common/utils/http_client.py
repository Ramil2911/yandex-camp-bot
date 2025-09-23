import httpx
import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, Union
from contextlib import asynccontextmanager

from common.config import config
from common.models import (
    SecurityCheckRequest, SecurityCheckResponse,
    RAGSearchRequest, RAGSearchResponse,
    DialogueRequest, DialogueResponse,
    LogEntry
)


logger = logging.getLogger(__name__)


class ServiceHTTPClient:
    """HTTP клиент для межсервисного взаимодействия (оптимизированный для serverless)"""

    def __init__(self, timeout: float = 10.0, retries: int = 1):
        # Сокращенные таймауты для serverless
        self.timeout = timeout
        self.retries = retries
        self._client: Optional[httpx.AsyncClient] = None

    @asynccontextmanager
    async def _get_client(self):
        """Получение HTTP клиента с connection pooling"""
        if self._client is None:
            # Оптимизированные настройки для serverless
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30
            )
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
                http2=True  # Включаем HTTP/2 для лучшей производительности
            )

        try:
            yield self._client
        except Exception as e:
            logger.error(f"HTTP client error: {str(e)}")
            raise
        finally:
            pass

    async def close(self):
        """Закрытие HTTP клиента"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: Optional[int] = None
    ) -> httpx.Response:
        """Выполнение HTTP запроса (упрощенная логика для serverless)"""

        # В serverless retry логика упрощается - только один быстрый повтор
        retry_count = min(retries or self.retries, 1)

        for attempt in range(retry_count + 1):
            try:
                async with self._get_client() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        data=data,
                        json=json,
                        headers=headers
                    )
                    return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < retry_count:
                    # Минимальная задержка для serverless
                    await asyncio.sleep(0.1)
                else:
                    logger.error(f"HTTP request failed: {str(e)}")
                    raise

        raise Exception(f"HTTP request failed after {retry_count + 1} attempts")

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """GET запрос"""
        return await self.request("GET", url, headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """POST запрос"""
        return await self.request("POST", url, data=data, json=json, headers=headers)

    async def put(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """PUT запрос"""
        return await self.request("PUT", url, data=data, json=json, headers=headers)

    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """DELETE запрос"""
        return await self.request("DELETE", url, headers=headers)

    def _get_trace_headers(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, str]:
        """Генерирует заголовки для трейсинга"""
        headers = {
            "X-Request-Id": str(uuid.uuid4())
        }

        if user_id:
            headers["X-User-Id"] = user_id
        if session_id:
            headers["X-Session-Id"] = session_id

        return headers

    async def check_security(self, request: SecurityCheckRequest) -> SecurityCheckResponse:
        """Проверка безопасности через Security Service"""
        try:
            headers = self._get_trace_headers(request.user_id, request.session_id)
            response = await self.request(
                "POST",
                f"{config.security_service_url}/moderate",
                json=request.dict(),
                headers=headers
            )
            response.raise_for_status()
            return SecurityCheckResponse(**response.json())
        except Exception as e:
            logger.error(f"Security service error: {e}")
            # Fallback: allow request if security service is down
            return SecurityCheckResponse(allowed=True, reason="Security service unavailable")

    async def search_rag(self, request: RAGSearchRequest) -> RAGSearchResponse:
        """Поиск в RAG системе"""
        try:
            headers = self._get_trace_headers(request.user_id, request.session_id)
            response = await self.request(
                "POST",
                f"{config.rag_service_url}/search",
                json=request.dict(),
                headers=headers
            )
            response.raise_for_status()
            return RAGSearchResponse(**response.json())
        except Exception as e:
            logger.error(f"RAG service error: {e}")
            # Fallback: empty context if RAG is down
            return RAGSearchResponse(
                context="",
                documents_found=0,
                search_time=0.0,
                documents_info=[],
                similarity_scores=[],
                error=f"RAG service error: {str(e)}"
            )

    async def process_dialogue(self, request: DialogueRequest) -> DialogueResponse:
        """Обработка диалога через Dialogue Service"""
        try:
            headers = self._get_trace_headers(request.user_id, request.session_id)
            response = await self.request(
                "POST",
                f"{config.dialogue_service_url}/dialogue",
                json=request.dict(),
                headers=headers
            )
            response.raise_for_status()
            return DialogueResponse(**response.json())
        except Exception as e:
            logger.error(f"Dialogue service error: {e}")
            return DialogueResponse(
                response="Извините, произошла ошибка при обработке запроса.",
                session_id=request.session_id,
                processing_time=0.0
            )

    async def clear_memory(self, session_id: str, user_id: str = "unknown") -> Dict[str, Any]:
        """Очистка памяти диалога"""
        try:
            headers = self._get_trace_headers(user_id=user_id, session_id=session_id)
            response = await self.request(
                "POST",
                f"{config.dialogue_service_url}/clear-memory",
                json={"session_id": session_id, "user_id": user_id},
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Clear memory error: {e}")
            return {"success": False, "message": str(e), "messages_cleared": 0}

    async def get_dialogue_history(self, session_id: str, limit: int = 50) -> Dict[str, Any]:
        """Получение истории диалога"""
        try:
            headers = self._get_trace_headers(session_id=session_id)
            response = await self.request(
                "GET",
                f"{config.dialogue_service_url}/dialogue/{session_id}/history",
                params={"limit": limit},
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get dialogue history error: {e}")
            return {"session_id": session_id, "history": [], "count": 0}

    async def search_dialogues_by_trace(self, trace_id: str) -> Dict[str, Any]:
        """Поиск диалогов по trace_id"""
        try:
            headers = self._get_trace_headers()
            response = await self.request(
                "GET",
                f"{config.dialogue_service_url}/dialogue/trace/{trace_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Search dialogues by trace error: {e}")
            return {"trace_id": trace_id, "dialogues": [], "count": 0}

    async def log_event(self, log_entry: LogEntry):
        """Отправка логов в Monitoring Service"""
        try:
            await self.request(
                "POST",
                f"{config.monitoring_service_url}/logs",
                json=log_entry.dict()
            )
        except Exception as e:
            logger.error(f"Monitoring service error: {e}")


# Глобальный экземпляр клиента с оптимизациями для serverless
service_http_client = ServiceHTTPClient(timeout=8.0, retries=0)  # Еще более агрессивные настройки


async def health_check_service(service_url: str, service_name: str) -> Dict[str, Any]:
    """Проверка здоровья сервиса"""
    try:
        response = await service_http_client.get(f"{service_url}/health")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Health check failed for {service_name}: {str(e)}")
        return {
            "status": "unhealthy",
            "service": service_name,
            "error": str(e)
        }
