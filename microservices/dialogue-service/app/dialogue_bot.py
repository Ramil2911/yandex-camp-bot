import time
import openai
from typing import Dict, Optional, List
from loguru import logger

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from .config import settings
from .models import SessionMemory, MemoryEntry, DialogueStats


class DialogueBot:
    """Диалоговый бот с поддержкой памяти разговоров"""

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.yc_openai_token,
            base_url=settings.model_config["api_base"]
        )

        # Хранение истории сессий в памяти (в продакшене использовать Redis)
        self.store: Dict[str, ChatMessageHistory] = {}

        # Статистика
        self.stats = DialogueStats(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_response_time=0.0,
            active_sessions=0,
            total_tokens_used=0
        )

        # Настройка LangChain цепочки
        self._setup_chain()

        logger.info("DialogueBot initialized")

    def _setup_chain(self):
        """Настройка цепочки для диалога с историей"""
        # Создаем промпт с поддержкой истории
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", settings.dialogue_config["system_prompt_template"]),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        # Создаем цепочку
        self.chain = self.prompt | self.client

        # Создаем цепочку с историей сообщений
        self.conversation = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="history"
        )

    def _get_session_history(self, session_id: str):
        """Получение истории сессии"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            self.stats.active_sessions = len(self.store)
        return self.store[session_id]

    def _prepare_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Подготовка контекста для промпта"""
        if not context:
            return ""

        rag_context = context.get("rag_context", "")
        documents_found = context.get("documents_found", 0)

        if rag_context and documents_found > 0:
            return f"\nНайденная информация ({documents_found} документов):\n{rag_context}"
        return ""

    async def process_message(self, message: str, session_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Обработка диалогового сообщения

        Args:
            message: Сообщение пользователя
            session_id: ID сессии
            context: Дополнительный контекст (RAG и т.д.)

        Returns:
            Dict с результатом обработки
        """
        start_time = time.time()
        self.stats.total_requests += 1

        try:
            # Подготовка контекста
            rag_context = self._prepare_context(context)

            # Формирование промпта с контекстом
            full_prompt = settings.dialogue_config["system_prompt_template"].format(
                context=rag_context,
                input=message
            )

            # Вызов YandexGPT через LangChain
            response = await self.conversation.ainvoke(
                {
                    "input": message,
                    "context": rag_context
                },
                config={"configurable": {"session_id": session_id}}
            )

            processing_time = time.time() - start_time
            self.stats.successful_requests += 1

            # Обновление статистики времени ответа
            total_time = self.stats.average_response_time * (self.stats.successful_requests - 1) + processing_time
            self.stats.average_response_time = total_time / self.stats.successful_requests

            # Извлечение информации о токенах (если доступно)
            tokens_used = getattr(response, 'usage', {}).get('total_tokens', 0)
            if tokens_used:
                self.stats.total_tokens_used += tokens_used

            result = {
                "response": response.content if hasattr(response, 'content') else str(response),
                "session_id": session_id,
                "processing_time": processing_time,
                "tokens_used": tokens_used,
                "context_used": bool(rag_context)
            }

            logger.info(
                f"Dialogue processed for session {session_id}: "
                f"time={processing_time:.2f}s, "
                f"context={result['context_used']}, "
                f"tokens={tokens_used}"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            self.stats.failed_requests += 1

            logger.error(
                f"Dialogue failed for session {session_id}: {str(e)} "
                f"(time: {processing_time:.2f}s)"
            )

            # Возвращаем fallback ответ
            return {
                "response": "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже.",
                "session_id": session_id,
                "processing_time": processing_time,
                "tokens_used": 0,
                "context_used": False,
                "error": str(e)
            }

    def clear_memory(self, session_id: str) -> int:
        """Очистка памяти разговора"""
        if session_id in self.store:
            message_count = len(self.store[session_id].messages)
            self.store[session_id].clear()
            logger.info(f"Memory cleared for session {session_id}: {message_count} messages")
            return message_count
        return 0

    def get_session_info(self, session_id: str) -> Optional[SessionMemory]:
        """Получение информации о сессии"""
        if session_id not in self.store:
            return None

        history = self.store[session_id]
        messages = []

        for msg in history.messages:
            messages.append(MemoryEntry(
                role=msg.type,
                content=msg.content,
                timestamp=time.time()  # В реальном проекте хранить timestamp сообщений
            ))

        return SessionMemory(
            session_id=session_id,
            messages=messages,
            created_at=time.time(),  # В реальном проекте хранить время создания
            last_accessed=time.time(),
            user_id="unknown"  # В реальном проекте связывать с user_id
        )

    def get_stats(self) -> DialogueStats:
        """Получение статистики бота"""
        return self.stats

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Очистка старых сессий"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        sessions_to_remove = []
        for session_id, history in self.store.items():
            # Проверяем время последнего доступа
            # В реальном проекте нужно хранить timestamp последнего доступа
            if current_time - time.time() > max_age_seconds:  # Заглушка
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.store[session_id]

        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")

        self.stats.active_sessions = len(self.store)
