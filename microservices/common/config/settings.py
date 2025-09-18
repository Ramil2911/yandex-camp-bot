import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings


class CommonSettings(BaseSettings):
    """Общие настройки для всех микросервисов"""

    # API Keys (должны быть переопределены в сервисах)
    yc_openai_token: Optional[str] = None
    yc_folder_id: Optional[str] = None
    telegram_token: Optional[str] = None

    # Database (для monitoring service)
    database_url: Optional[str] = None

    # Service URLs
    security_service_url: str = "http://security-service:8001"
    rag_service_url: str = "http://rag-service:8002"
    dialogue_service_url: str = "http://dialogue-service:8003"
    monitoring_service_url: str = "http://monitoring-service:8004"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Common model configurations
    default_model_config = {
        "model_name": "yandexgpt-lite/latest",
        "temperature": 0.6,
        "max_tokens": 2000,
        "api_base": "https://llm.api.cloud.yandex.net/v1"
    }

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Rate limiting (для API Gateway)
    rate_limit_requests: int = 10
    rate_limit_window: int = 60  # seconds

    # Security
    security_config = {
        "max_request_length": 1000,
        "suspicious_words_threshold": 3,
        "block_suspicious": True
    }

    # RAG configuration
    rag_config = {
        "enabled": True,
        "max_documents": 3,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "embedding_model": "all-MiniLM-L6-v2",
        "similarity_threshold": 0.6,
        "min_documents": 1,
        "max_search_results": 5
    }

    # Monitoring configuration
    monitoring_config = {
        "log_retention_days": 30,
        "max_logs_per_request": 1000,
        "enable_metrics": True,
        "metrics_retention_hours": 24
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Глобальный экземпляр настроек
common_settings = CommonSettings()
