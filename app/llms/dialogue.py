import time
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from app.llms.base import LLMBase
from app.security.moderator import LLMModerator
from app.utils.config import SYSTEM_PROMPT
from app.utils.log import logger, log_user_action, log_error, log_system_event, log_bot_startup


class DialogueBot(LLMBase):
    """Диалоговый бот на базе YandexGPT с поддержкой истории разговоров"""

    def __init__(self,
                 folder_id: str = None,
                 openai_api_key: str = None,
                 system_prompt: str = None):
        super().__init__(
            folder_id=folder_id,
            openai_api_key=openai_api_key,
            component_name="dialogue_bot"
        )

        # Системный промпт
        self.system_prompt = system_prompt or SYSTEM_PROMPT

        # Инициализируем модератор
        log_bot_startup("moderator_init", "Initializing security moderator")
        self.moderator = LLMModerator(folder_id, openai_api_key)
        log_bot_startup("moderator_ready", "Security moderator initialized")

        # Настраиваем диалоговую цепочку
        log_bot_startup("dialogue_chain", "Setting up dialogue chain with message history")
        self._setup_dialogue_chain()

        # Словарь для хранения истории сессий
        self.store = {}

        # Статистика
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "malicious_requests": 0,
            "total_response_time": 0.0,
            "active_sessions": 0
        }

        log_bot_startup("dialogue_bot_ready", "DialogueBot initialization completed")

    def _setup_dialogue_chain(self):
        """Настройка цепочки для диалога с историей"""
        # Создаем промпт с поддержкой истории
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        # Создаем цепочку с поддержкой истории
        self.chain = self.prompt | self.llm

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
            self.stats["active_sessions"] = len(self.store)
        return self.store[session_id]

    def process_request(self, question: str, session_id: str = "default") -> str:
        """
        Обработка диалогового запроса

        Args:
            question: Вопрос пользователя
            session_id: ID сессии

        Returns:
            str: Ответ от LLM
        """
        return self.ask_gpt(question, session_id)

    def ask_gpt(self, question: str, session_id: str = "default") -> str:
        """Запрос к YandexGPT через LangChain"""
        start_time = time.time()
        self.stats["total_requests"] += 1

        try:
            # Используем современную цепочку с историей
            response = self.conversation.invoke(
                {"input": question},
                config={"configurable": {"session_id": session_id}}
            )

            duration = time.time() - start_time
            self.stats["successful_requests"] += 1
            self.stats["total_response_time"] += duration

            return response.content

        except Exception as e:
            duration = time.time() - start_time
            self.stats["failed_requests"] += 1
            log_error(session_id, session_id, f"GPT request failed: {str(e)}")
            raise

    def clear_memory(self, session_id: str = "default"):
        """Очистка памяти разговора"""
        if session_id in self.store:
            message_count = len(self.store[session_id].messages)
            self.store[session_id].clear()
            log_user_action(session_id, session_id, "memory_cleared", f"{message_count} messages")

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики бота"""
        avg_response_time = (
            self.stats["total_response_time"] / self.stats["successful_requests"]
            if self.stats["successful_requests"] > 0 else 0
        )

        stats = {
            **self.stats,
            "average_response_time": avg_response_time,
            "success_rate": (
                self.stats["successful_requests"] / self.stats["total_requests"]
                if self.stats["total_requests"] > 0 else 0
            )
        }

        return stats

    def get_dialogue_info(self) -> Dict[str, Any]:
        """Получение информации о диалоговом боте"""
        return {
            **self.get_llm_info(),
            "system_prompt_length": len(self.system_prompt),
            "active_sessions": self.stats["active_sessions"],
            "total_requests": self.stats["total_requests"]
        }


# Создаем глобальный экземпляр бота для совместимости
def create_dialogue_bot():
    """Фабричная функция для создания экземпляра диалогового бота"""
    return DialogueBot()


# Глобальный экземпляр (создается при импорте)
dialogue_bot = create_dialogue_bot()
