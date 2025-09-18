import time
from typing import Dict, Optional, List, Any
from loguru import logger

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.chat_models import ChatOpenAI

from common.config import config
from .models import SessionMemory, MemoryEntry, DialogueStats


class DialogueBot:
    """Диалоговый бот с поддержкой памяти разговоров"""

    def __init__(self):
        # Инициализация с обработкой ошибок
        self.client = None
        self.llm_status = "unavailable"
        
        try:
            # Проверяем наличие токенов
            if not config.yc_openai_token:
                raise ValueError("YC_OPENAI_TOKEN not provided")
            if not config.yc_folder_id:
                raise ValueError("YC_FOLDER_ID not provided")
                
            # Получаем конфигурацию модели с проверкой
            model_config = getattr(config, 'model_config', {
                "model_name": "yandexgpt-lite/latest",
                "temperature": 0.6,
                "max_tokens": 2000,
                "api_base": "https://llm.api.cloud.yandex.net/v1"
            })

            # Используем правильный формат модели для Yandex Cloud
            model_name = f"gpt://{config.yc_folder_id}/yandexgpt-lite/latest"

            self.client = ChatOpenAI(
                openai_api_key=config.yc_openai_token,
                openai_api_base=model_config.get("api_base", "https://llm.api.cloud.yandex.net/v1"),
                model_name=model_name,
                temperature=model_config.get("temperature", 0.6),
                max_tokens=model_config.get("max_tokens", 2000)
            )
            
            # Тестируем подключение
            self._test_llm_connection()
            self.llm_status = "available"
            logger.info("DialogueBot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DialogueBot: {e}")
            self.llm_status = "unavailable"
            self.client = None

        # Хранение истории сессий в памяти (в продакшене использовать Redis)
        self.store: Dict[str, ChatMessageHistory] = {}
        # Хранение времени последнего доступа к сессиям
        self.session_timestamps: Dict[str, float] = {}
        # Хранение user_id для каждой сессии
        self.session_users: Dict[str, str] = {}

        # Статистика
        self.stats = DialogueStats(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_response_time=0.0,
            active_sessions=0,
            total_tokens_used=0
        )

        # Настройка LangChain цепочки только если LLM доступен
        if self.llm_status == "available":
            self._setup_chain()

    def _test_llm_connection(self):
        """Тестирование подключения к LLM"""
        try:
            # Простой тестовый запрос
            test_response = self.client.invoke("test")
            logger.info("LLM connection test successful")
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
            raise

    def _setup_chain(self):
        """Настройка цепочки для диалога с историей"""
        # Создаем промпт с поддержкой истории
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", config.dialogue_config["system_prompt_template"]),
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

    def _initialize_session(self, session_id: str, user_id: str):
        """Инициализация новой сессии с user_id"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            self.session_users[session_id] = user_id
            self.stats.active_sessions = len(self.store)
            logger.info(f"New session initialized: {session_id} for user: {user_id}")

    def _get_session_history(self, session_id: str):
        """Получение истории сессии"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            self.stats.active_sessions = len(self.store)

        # Обновляем timestamp последнего доступа
        self.session_timestamps[session_id] = time.time()
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

    async def process_message(self, message: str, session_id: str, user_id: str = "unknown", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Обработка диалогового сообщения

        Args:
            message: Сообщение пользователя
            session_id: ID сессии
            user_id: ID пользователя (по умолчанию "unknown")
            context: Дополнительный контекст (RAG и т.д.)

        Returns:
            Dict с результатом обработки
        """
        start_time = time.time()
        self.stats.total_requests += 1

        # Инициализируем сессию с user_id
        self._initialize_session(session_id, user_id)

        try:
            # Подготовка контекста
            rag_context = self._prepare_context(context)

            # Формирование промпта с контекстом
            full_prompt = config.dialogue_config["system_prompt_template"].format(
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
            # Удаляем связанные данные при очистке сессии
            if session_id in self.session_timestamps:
                del self.session_timestamps[session_id]
            if session_id in self.session_users:
                del self.session_users[session_id]
            logger.info(f"Memory cleared for session {session_id}: {message_count} messages")
            return message_count
        return 0

    def get_dialogue_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение истории диалога для API"""
        if session_id not in self.store:
            return []

        history = self.store[session_id]
        messages = []

        for msg in history.messages[-limit:]:  # Берем последние limit сообщений
            messages.append({
                "role": msg.type,
                "content": msg.content,
                "timestamp": time.time()
            })

        return messages

    def search_dialogues_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Поиск диалогов по trace_id (заглушка, пока нет реализации трейсинга)"""
        # В текущей реализации нет системы трейсинга, поэтому возвращаем пустой результат
        logger.warning(f"Trace search not implemented yet for trace_id: {trace_id}")
        return []

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
                timestamp=time.time()
            ))

        return SessionMemory(
            session_id=session_id,
            messages=messages,
            created_at=time.time(),
            last_accessed=self.session_timestamps.get(session_id, time.time()),
            user_id=self.session_users.get(session_id, "unknown")
        )

    def get_stats(self) -> DialogueStats:
        """Получение статистики бота"""
        return self.stats

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Очистка старых сессий"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        sessions_to_remove = []
        for session_id in list(self.store.keys()):
            # Проверяем время последнего доступа из session_timestamps
            last_access = self.session_timestamps.get(session_id, current_time)
            if current_time - last_access > max_age_seconds:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            del self.store[session_id]
            # Удаляем связанные данные
            if session_id in self.session_timestamps:
                del self.session_timestamps[session_id]
            if session_id in self.session_users:
                del self.session_users[session_id]

        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")

        self.stats.active_sessions = len(self.store)
