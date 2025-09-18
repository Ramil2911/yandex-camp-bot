"""
RAG-адаптер для интеграции с диалоговым ботом.
Обеспечивает поиск релевантной информации и передачу контекста в LLM.
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from .rag_system import RAGSystem
from .rag_config import RAG_CONFIG


class RAGAdapter:
    """
    Адаптер для интеграции RAG системы с диалоговым ботом.
    Обеспечивает поиск релевантной информации и формирование контекста.
    """
    
    def __init__(self, 
                 persist_directory: str = None, 
                 data_directory: str = None,
                 enabled: bool = None):
        """
        Инициализация RAG адаптера
        
        Args:
            persist_directory: Директория для хранения векторной БД
            data_directory: Директория с документами
            enabled: Включен ли RAG
        """
        self.enabled = enabled if enabled is not None else RAG_CONFIG["enabled"]
        self.rag_system = None
        self.stats = {
            "rag_queries": 0,
            "rag_successes": 0,
            "rag_errors": 0,
            "documents_loaded": 0,
            "average_context_length": 0.0
        }
        
        if self.enabled:
            try:
                logger.info("Инициализация RAG системы...")
                self.rag_system = RAGSystem(
                    persist_directory=persist_directory or RAG_CONFIG["persist_directory"],
                    data_directory=data_directory or RAG_CONFIG["data_directory"]
                )
                
                # Инициализируем RAG синхронно, если нет event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Если есть event loop, создаем задачу
                    loop.create_task(self._initialize_rag())
                except RuntimeError:
                    # Если нет event loop, инициализируем синхронно
                    asyncio.run(self._initialize_rag())
                
                logger.info("RAG система инициализирована")
                
            except Exception as e:
                logger.error(f"Ошибка инициализации RAG: {e}")
                self.enabled = False
        else:
            logger.info("RAG отключен")
    
    async def _initialize_rag(self):
        """Асинхронная инициализация RAG системы"""
        try:
            if self.rag_system:
                await self.rag_system.add_documents()
                self.stats["documents_loaded"] = self.rag_system.get_document_count()
                logger.info(f"Загружено {self.stats['documents_loaded']} документов в RAG")
        except Exception as e:
            logger.error(f"Ошибка загрузки документов в RAG: {e}")
            self.enabled = False
    
    async def get_relevant_context(self, query: str, max_docs: int = None, similarity_threshold: float = None) -> str:
        """
        Получение релевантного контекста для запроса с пороговой фильтрацией
        
        Args:
            query: Запрос пользователя
            max_docs: Максимальное количество документов
            similarity_threshold: Порог схожести (0.0-1.0), None для использования из конфигурации
            
        Returns:
            str: Релевантный контекст или пустая строка
        """
        if not self.enabled or not self.rag_system:
            return ""
        
        max_docs = max_docs or RAG_CONFIG["max_documents"]
        self.stats["rag_queries"] += 1
        
        try:
            # Ищем релевантные документы с пороговой фильтрацией
            relevant_docs = await self.rag_system.search_relevant_docs(
                query=query, 
                k=max_docs,
                similarity_threshold=similarity_threshold
            )
            
            if not relevant_docs:
                logger.debug(f"Не найдено релевантных документов для запроса: {query[:50]}...")
                return ""
            
            # Формируем контекст
            context_parts = []
            for i, doc in enumerate(relevant_docs, 1):
                context_parts.append(f"Документ {i}:\n{doc}\n")
            
            context = "\n".join(context_parts)
            
            # Обновляем статистику
            self.stats["rag_successes"] += 1
            self.stats["average_context_length"] = (
                (self.stats["average_context_length"] * (self.stats["rag_successes"] - 1) + len(context)) 
                / self.stats["rag_successes"]
            )
            
            logger.debug(f"Найдено {len(relevant_docs)} релевантных документов для запроса")
            return context
            
        except Exception as e:
            self.stats["rag_errors"] += 1
            logger.error(f"Ошибка поиска в RAG: {e}")
            return ""
    
    def format_rag_prompt(self, user_query: str, context: str) -> str:
        """
        Форматирование промпта с RAG контекстом
        
        Args:
            user_query: Запрос пользователя
            context: Релевантный контекст
            
        Returns:
            str: Отформатированный промпт
        """
        if not context:
            return user_query
        
        rag_prompt = f"""Используй следующую информацию для ответа на вопрос пользователя:

{context}

Вопрос пользователя: {user_query}

Ответь на основе предоставленной информации. Если информация не релевантна, отвечай как обычно."""
        
        return rag_prompt
    
    async def process_with_rag(self, user_query: str, max_docs: int = None) -> Dict[str, Any]:
        """
        Обработка запроса с использованием RAG
        
        Args:
            user_query: Запрос пользователя
            max_docs: Максимальное количество документов
            
        Returns:
            Dict: Результат обработки с контекстом
        """
        result = {
            "original_query": user_query,
            "context": "",
            "enhanced_query": user_query,
            "rag_used": False
        }
        
        if not self.enabled:
            return result
        
        # Получаем релевантный контекст
        context = await self.get_relevant_context(user_query, max_docs)
        
        if context:
            result["context"] = context
            result["enhanced_query"] = self.format_rag_prompt(user_query, context)
            result["rag_used"] = True
            logger.debug("RAG контекст добавлен к запросу")
        
        return result
    
    def get_rag_stats(self) -> Dict[str, Any]:
        """Получение статистики RAG системы"""
        success_rate = (
            self.stats["rag_successes"] / self.stats["rag_queries"]
            if self.stats["rag_queries"] > 0 else 0
        )
        
        return {
            **self.stats,
            "enabled": self.enabled,
            "success_rate": success_rate
        }
    
    def toggle_rag(self, enabled: bool):
        """Включение/отключение RAG"""
        self.enabled = enabled
        logger.info(f"RAG {'включен' if enabled else 'отключен'}")
    
    async def reload_documents(self):
        """Перезагрузка документов в RAG"""
        if not self.enabled or not self.rag_system:
            logger.warning("RAG отключен, перезагрузка невозможна")
            return
        
        try:
            logger.info("Перезагрузка документов в RAG...")
            self.rag_system.reload_documents()
            await self._initialize_rag()
            logger.info("Документы успешно перезагружены")
        except Exception as e:
            logger.error(f"Ошибка перезагрузки документов: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Получение информации о RAG системе"""
        info = {
            "enabled": self.enabled,
            "stats": self.get_rag_stats(),
            "similarity_threshold": RAG_CONFIG.get("similarity_threshold", 0.7)
        }
        
        if self.rag_system:
            info["vectorstore_info"] = self.rag_system.get_vectorstore_info()
        
        return info
    
    def set_similarity_threshold(self, threshold: float):
        """
        Установка порога схожести для фильтрации документов
        
        Args:
            threshold: Порог схожести (0.0-1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Порог схожести должен быть между 0.0 и 1.0")
        
        RAG_CONFIG["similarity_threshold"] = threshold
        logger.info(f"Порог схожести установлен: {threshold:.3f}")
    
    def get_similarity_threshold(self) -> float:
        """Получение текущего порога схожести"""
        return RAG_CONFIG.get("similarity_threshold", 0.7)
