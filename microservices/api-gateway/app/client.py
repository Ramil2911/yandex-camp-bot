import httpx
import json
import logging
from typing import Optional, Dict, Any
from .config import settings
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

    async def check_security(self, request: SecurityCheckRequest) -> SecurityCheckResponse:
        """Проверка безопасности через Security Service"""
        try:
            response = await self.client.post(
                f"{settings.security_service_url}/moderate",
                json=request.dict()
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
            response = await self.client.post(
                f"{settings.rag_service_url}/search",
                json=request.dict()
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
            response = await self.client.post(
                f"{settings.dialogue_service_url}/dialogue",
                json=request.dict()
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
                f"{settings.monitoring_service_url}/logs",
                json=log_entry.dict()
            )
        except Exception as e:
            logger.error(f"Monitoring service error: {e}")

    async def close(self):
        """Закрытие HTTP клиента"""
        await self.client.aclose()


# Глобальный экземпляр клиента
service_client = ServiceClient()
