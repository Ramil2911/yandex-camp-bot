"""
RAG этап для пайплайна обработки сообщений.
Обеспечивает поиск релевантной информации и обогащение контекста.
"""

import asyncio
from typing import Dict, Any
from loguru import logger

from app.rag import RAGAdapter, RAG_CONFIG
from app.utils.log import log_user_action, log_error


class RAGPipelineStage:
    """
    RAG этап для пайплайна обработки сообщений.
    Обеспечивает поиск релевантной информации и обогащение контекста запроса.
    """
    
    def __init__(self, rag_adapter: RAGAdapter = None):
        """
        Инициализация RAG этапа
        
        Args:
            rag_adapter: Адаптер RAG системы (если None, создается новый)
        """
        self.rag_adapter = rag_adapter or RAGAdapter()
        self.stats = {
            "rag_requests": 0,
            "rag_successes": 0,
            "rag_errors": 0,
            "context_added": 0,
            "average_context_length": 0.0
        }
        
        logger.info("RAG этап пайплайна инициализирован")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка запроса через RAG этап
        
        Args:
            input_data: Данные запроса (message, user_id, session_id, etc.)
            
        Returns:
            Dict: Обновленные данные с RAG контекстом
        """
        message = input_data.get("message", "")
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "unknown")
        
        self.stats["rag_requests"] += 1
        
        # Если RAG отключен, пропускаем этап
        if not self.rag_adapter.enabled:
            logger.debug("RAG отключен, пропускаем этап")
            return {
                **input_data,
                "rag_context": "",
                "rag_used": False,
                "pipeline_stage": "rag_skipped"
            }
        
        try:
            # Получаем RAG контекст
            rag_result = await self.rag_adapter.process_with_rag(
                message, 
                max_docs=RAG_CONFIG["max_documents"]
            )
            
            # Обновляем статистику
            if rag_result["rag_used"]:
                self.stats["rag_successes"] += 1
                self.stats["context_added"] += 1
                
                # Обновляем среднюю длину контекста
                context_length = len(rag_result["context"])
                self.stats["average_context_length"] = (
                    (self.stats["average_context_length"] * (self.stats["context_added"] - 1) + context_length) 
                    / self.stats["context_added"]
                )
                
                # Логируем использование RAG
                log_user_action(
                    user_id, 
                    session_id, 
                    "rag_context_added", 
                    f"Context length: {context_length}"
                )
                
                logger.debug(f"RAG контекст добавлен: {context_length} символов")
            else:
                logger.debug("RAG не нашел релевантной информации")
            
            return {
                **input_data,
                "rag_context": rag_result["context"],
                "rag_used": rag_result["rag_used"],
                "enhanced_message": rag_result["enhanced_query"],
                "pipeline_stage": "rag_processed"
            }
            
        except Exception as e:
            self.stats["rag_errors"] += 1
            log_error(user_id, session_id, f"RAG этап failed: {str(e)}")
            
            return {
                **input_data,
                "rag_context": "",
                "rag_used": False,
                "enhanced_message": message,
                "pipeline_stage": "rag_error",
                "rag_error": str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики RAG этапа"""
        success_rate = (
            self.stats["rag_successes"] / self.stats["rag_requests"]
            if self.stats["rag_requests"] > 0 else 0
        )
        
        return {
            **self.stats,
            "success_rate": success_rate,
            "rag_adapter_stats": self.rag_adapter.get_rag_stats()
        }
    
    def toggle_rag(self, enabled: bool):
        """Включение/отключение RAG"""
        self.rag_adapter.toggle_rag(enabled)
        logger.info(f"RAG этап {'включен' if enabled else 'отключен'}")
    
    async def reload_documents(self):
        """Перезагрузка документов в RAG"""
        await self.rag_adapter.reload_documents()
        logger.info("Документы RAG перезагружены")


# Глобальный экземпляр RAG этапа
rag_pipeline_stage = RAGPipelineStage()
