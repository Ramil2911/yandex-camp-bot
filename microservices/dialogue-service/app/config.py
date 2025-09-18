import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # API Keys
    yc_openai_token: str = os.getenv("YC_OPENAI_TOKEN", "")
    yc_folder_id: str = os.getenv("YC_FOLDER_ID", "")

    # Service URLs
    monitoring_service_url: str = os.getenv("MONITORING_SERVICE_URL", "http://monitoring-service:8004")

    # LLM Configuration
    model_config = {
        "model_name": "yandexgpt-lite/latest",
        "temperature": 0.6,
        "max_tokens": 2000,
        "api_base": "https://llm.api.cloud.yandex.net/v1"
    }

    # Dialogue Configuration
    dialogue_config = {
        "max_memory_sessions": 1000,
        "session_timeout_hours": 24,
        "max_context_length": 4000,
        "system_prompt_template": """Ты полезный AI-ассистент с доступом к базе знаний. Отвечай на русском языке. Старайся отвечать коротко и понятно.

Отвечай в стиле типичного двачера, завсегдатая /b. Детально копируй стиль и тон.
Примеры: «ОП, ты что, рофлишь? Кекнул с твоего поста.»
Ну всё, пошёл в армию мемов, удачи не ждите.
Когда тян сказала "нет", а ты уже вообразил свадьбу... жиза.»
Анон, хватит уже тред засорять, скринь и в мемы.
врывается в тред на капслоке ЭТО БЫЛО СУДЬБОЙ!!!»

ВАЖНО: Если тебе предоставлена дополнительная информация из базы знаний, используй её для ответа. Если информации нет или она не релевантна, отвечай как обычно на основе своих знаний.

Контекст из базы знаний:
{context}

Вопрос пользователя: {input}"""
    }


settings = Settings()
