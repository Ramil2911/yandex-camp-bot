import time
from typing import Dict, List, Optional, Any
from loguru import logger

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from common.llm import LLMBase
from common.utils.tracing_middleware import log_error
from common.config import config
from .models import QueryAnalysisResult


class QueryProcessor(LLMBase):
    """Компонент для анализа и перефразирования запросов с использованием LLM"""

    def __init__(self):
        # Валидация folder_id
        if not config.yc_folder_id or not config.yc_folder_id.strip():
            raise ValueError("yc_folder_id is required and cannot be empty for QueryProcessor")

        # Конфигурация для анализа запросов
        query_processor_config = {
            "model_name": "yandexgpt-lite/latest",
            "temperature": 0.3,  # Низкая температура для детерминированных ответов
            "max_tokens": 1000,
            "api_base": "https://llm.api.cloud.yandex.net/v1"
        }

        super().__init__(
            folder_id=config.yc_folder_id,
            openai_api_key=config.yc_openai_token,
            model_config=query_processor_config,
            component_name="query_processor"
        )

        # Инициализируем цепочку обработки запросов
        self._setup_processing_chain()

    def _setup_processing_chain(self):
        """Настройка цепочки для обработки запросов"""
        try:
            # Пытаемся использовать structured output
            self.analysis_chain = (
                ChatPromptTemplate.from_messages([
                    ("system", """Ты — интеллектуальный анализатор запросов для системы поиска информации.
Твоя задача — определить, нужен ли поиск в базе знаний (RAG) для данного запроса пользователя, и если да, то создать перефразированные версии запроса для более эффективного поиска.

Правила анализа:
1. RAG НУЖЕН если запрос касается:
   - Фактологических вопросов о конкретных темах
   - Поиска информации, инструкций или руководств
   - Вопросов о технологиях, методах, алгоритмах
   - Конкретных данных или примеров из документов

2. RAG НЕ НУЖЕН если запрос касается:
   - Общих разговоров или приветствий
   - Математических расчетов или вычислений
   - Личного мнения или советов
   - Творческих задач
   - Вопросов о текущих событиях (не из базы знаний)

Если RAG требуется, создай 1-3 перефразированных запроса, которые:
- Используют синонимы и альтернативные формулировки
- Разбивают сложные запросы на более простые компоненты
- Добавляют ключевые слова для лучшего поиска
- Сохраняют исходный смысл, но улучшают поисковую эффективность"""),
                    ("human", "Запрос пользователя: {query}")
                ])
                | self.llm.with_structured_output(QueryAnalysisResult)
            )
            self._has_strict_schema = True
            logger.info("QueryProcessor initialized with structured output support")

        except Exception as e:
            logger.warning(f"Structured output not available, falling back to JSON parsing: {e}")

            # Фолбэк: просим JSON и парсим вручную
            self.analysis_chain = (
                ChatPromptTemplate.from_messages([
                    ("system", """Ты — интеллектуальный анализатор запросов для системы поиска информации.
Твоя задача — определить, нужен ли поиск в базе знаний (RAG) для данного запроса пользователя, и если да, то создать перефразированные версии запроса для более эффективного поиска.

Правила анализа:
1. RAG НУЖЕН если запрос касается:
   - Фактологических вопросов о конкретных темах
   - Поиска информации, инструкций или руководств
   - Вопросов о технологиях, методах, алгоритмах
   - Конкретных данных или примеров из документов

2. RAG НЕ НУЖЕН если запрос касается:
   - Общих разговоров или приветствий
   - Математических расчетов или вычислений
   - Личного мнения или советов
   - Творческих задач
   - Вопросов о текущих событиях (не из базы знаний)

Если RAG требуется, создай 1-3 перефразированных запроса, которые:
- Используют синонимы и альтернативные формулировки
- Разбивают сложные запросы на более простые компоненты
- Добавляют ключевые слова для лучшего поиска
- Сохраняют исходный смысл, но улучшают поисковую эффективность

Ответ должен быть строго в формате JSON с полями:
- rag_required: true/false
- reasoning: краткое объяснение решения
- rephrased_queries: массив строк (пустой, если RAG не требуется)"""),
                    ("human", "Запрос пользователя: {query}\nВерни JSON.")
                ])
                | self.llm
            )
            self._parser = JsonOutputParser(pydantic_object=QueryAnalysisResult)
            self._has_strict_schema = False
            logger.info("QueryProcessor initialized with JSON fallback")

    async def process_request(self, query: str, user_id: str, session_id: str) -> QueryAnalysisResult:
        """
        Обработка запроса анализатором (реализация абстрактного метода)

        Args:
            query: Исходный запрос пользователя
            user_id: ID пользователя
            session_id: ID сессии

        Returns:
            QueryAnalysisResult с результатом анализа
        """
        try:
            if self._has_strict_schema:
                result: QueryAnalysisResult = await self.analysis_chain.ainvoke({"query": query})
            else:
                raw = await self.analysis_chain.ainvoke({"query": query})
                result = self._parser.parse(raw.content)

            # Логируем результаты анализа
            logger.info(
                f"Query analysis for user {user_id}: "
                f"RAG={result.rag_required}, "
                f"rephrasings={len(result.rephrased_queries)}"
            )

            # Ограничиваем количество перефразирований до 3
            if len(result.rephrased_queries) > 3:
                result.rephrased_queries = result.rephrased_queries[:3]

            return result

        except Exception as e:
            error_message = f"Query analysis failed: {str(e)}"
            logger.error(error_message)

            # Отправляем ошибку в monitoring-service
            log_error(
                service="rag-service",
                error_type="QueryAnalysisError",
                error_message=error_message,
                user_id=user_id,
                session_id=session_id,
                context={
                    "operation": "query_analysis",
                    "component": "QueryProcessor",
                    "query_length": len(query) if query else 0
                }
            )

            # В случае ошибки возвращаем результат без RAG
            logger.warning(f"Query analysis error fallback for user {user_id}")

            return QueryAnalysisResult(
                rag_required=False,
                reasoning="Ошибка анализа, применена политика по умолчанию (без RAG).",
                rephrased_queries=[]
            )

    async def analyze_and_rephrase_query(self, query: str, user_id: str, session_id: str = "unknown") -> QueryAnalysisResult:
        """Удобный алиас для process_request"""
        return await self.process_request(query, user_id, session_id)

    def get_processor_stats(self) -> Dict[str, Any]:
        """Получение статистики процессора запросов"""
        return {
            **self.get_llm_info(),
            "structured_output": self._has_strict_schema,
            "analysis_version": "1.0"
        }

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики для health check"""
        return self.get_processor_stats()
