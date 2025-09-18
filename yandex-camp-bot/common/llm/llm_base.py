from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)


class LLMBase(ABC):
    """Абстрактный базовый класс для всех LLM компонентов"""

    def __init__(self,
                 folder_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 model_config: Optional[Dict[str, Any]] = None,
                 component_name: str = "llm_component"):
        """
        Инициализация базового LLM

        Args:
            folder_id: ID каталога Yandex Cloud
            openai_api_key: API ключ для YandexGPT
            model_config: Конфигурация модели
            component_name: Имя компонента для логирования
        """
        self.component_name = component_name

        try:
            # Используем переданные параметры или значения по умолчанию из конфига
            self.folder_id = folder_id
            self.openai_api_key = openai_api_key
            self.model_config = model_config or {
                "model_name": "yandexgpt-lite/latest",
                "temperature": 0.6,
                "max_tokens": 2000,
                "api_base": "https://llm.api.cloud.yandex.net/v1"
            }

            if not self.folder_id or not self.openai_api_key:
                raise ValueError("folder_id and openai_api_key are required")

            # Создаем базовый LLM
            self.llm = self._create_llm()
            model_name = self._get_model_name()

            logger.info(f"{component_name} initialized with {model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize {component_name}: {str(e)}")
            raise

    def _create_llm(self) -> ChatOpenAI:
        """Создание экземпляра ChatOpenAI с базовой конфигурацией"""
        return ChatOpenAI(
            model=self._get_model_name(),
            openai_api_key=self.openai_api_key,
            openai_api_base=self.model_config['api_base'],
            temperature=self.model_config.get('temperature', 0.6),
            max_tokens=self.model_config.get('max_tokens', 2000)
        )

    def _get_model_name(self) -> str:
        """Получение полного имени модели"""
        return f"gpt://{self.folder_id}/{self.model_config['model_name']}"

    @abstractmethod
    def process_request(self, *args, **kwargs):
        """
        Абстрактный метод для обработки запросов.
        Должен быть реализован в дочерних классах.
        """
        pass

    def get_llm_info(self) -> Dict[str, Any]:
        """Получение информации о LLM конфигурации"""
        return {
            "component_name": self.component_name,
            "model": self._get_model_name(),
            "temperature": self.model_config.get('temperature'),
            "max_tokens": self.model_config.get('max_tokens'),
            "api_base": self.model_config.get('api_base')
        }

    def update_config(self, **kwargs):
        """Обновление конфигурации LLM"""
        for key, value in kwargs.items():
            if key in self.model_config:
                self.model_config[key] = value
                logger.info(f"Updated {key} to {value} for {self.component_name}")

        # Пересоздаем LLM с новой конфигурацией
        if any(key in ['temperature', 'max_tokens'] for key in kwargs):
            self.llm = self._create_llm()
            logger.info(f"Recreated LLM instance for {self.component_name} with new config")
