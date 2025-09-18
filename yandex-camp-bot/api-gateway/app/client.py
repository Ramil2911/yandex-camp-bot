import httpx
import json
import logging
import uuid
from typing import Optional, Dict, Any
from common.config import config
from .models import (
    SecurityCheckRequest, SecurityCheckResponse,
    DialogueRequest, DialogueResponse,
    RAGSearchRequest, RAGSearchResponse,
    LogEntry
)

logger = logging.getLogger(__name__)


class ServiceClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def _get_trace_headers(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, str]:
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
            headers = await self._get_trace_headers(request.user_id, request.session_id)
            response = await self.client.post(
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
            headers = await self._get_trace_headers(request.user_id, request.session_id)
            response = await self.client.post(
                f"{config.rag_service_url}/search",
                json=request.dict(),
                headers=headers
            )
            response.raise_for_status()
            return RAGSearchResponse(**response.json())
        except Exception as e:
            logger.error(f"RAG service error: {e}")
            # Fallback: empty context if RAG is down
            return RAGSearchResponse(context="", documents_found=0, search_time=0.0)

    async def process_dialogue(self, request: DialogueRequest) -> DialogueResponse:
        """Обработка диалога через Dialogue Service"""
        try:
            headers = await self._get_trace_headers(request.user_id, request.session_id)
            response = await self.client.post(
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
                session_id=request.session_id
            )

    async def log_event(self, log_entry: LogEntry):
        """Отправка логов в Monitoring Service"""
        try:
            await self.client.post(
                f"{config.monitoring_service_url}/logs",
                json=log_entry.dict()
            )
        except Exception as e:
            logger.error(f"Monitoring service error: {e}")

    async def close(self):
        """Закрытие HTTP клиента"""
        await self.client.aclose()


# Глобальный экземпляр клиента
service_client = ServiceClient()
