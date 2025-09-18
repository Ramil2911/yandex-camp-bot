import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # API Keys
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")

    # Service URLs
    security_service_url: str = os.getenv("SECURITY_SERVICE_URL", "http://security-service:8001")
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "http://rag-service:8002")
    dialogue_service_url: str = os.getenv("DIALOGUE_SERVICE_URL", "http://dialogue-service:8003")
    monitoring_service_url: str = os.getenv("MONITORING_SERVICE_URL", "http://monitoring-service:8004")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Rate limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60  # seconds

    # Bot messages
    bot_messages = {
        "start": """Привет! Я бот для работы с Yandex GPT.
Я помню наш разговор! Просто напиши мне свой вопрос.

Доступные команды:
/clear - очистить память разговора
/help - показать справку
/stats - показать статистику бота
/rag - показать статус RAG системы""",

        "help": """🤖 **YandexGPT Bot**

**Команды:**
/start - начать работу
/clear - очистить память разговора
/help - показать эту справку
/stats - показать статистику бота
/rag - показать статус RAG системы

Просто напишите ваш вопрос, и я отвечу!""",

        "memory_cleared": "Память разговора очищена!",
        "empty_message": "Пожалуйста, введите вопрос",
        "malicious_blocked": "Извините, я не могу ответить на этот вопрос.",
        "moderator_blocked": "Извините, я не могу ответить на это.",
        "error": """Извините, произошла ошибка при обработке вашего запроса.
Пожалуйста, попробуйте позже.""",
        "telegram_error": "Произошла ошибка. Пожалуйста, попробуйте позже."
    }


settings = Settings()
