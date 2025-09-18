"""
Главный LangChain пайплайн для обработки сообщений Telegram бота.
Объединяет безопасность, сессии и диалог в единую цепочку.
"""

import time
from typing import Dict, Any, Optional
from langchain_core.runnables import (
    RunnableLambda, 
    RunnablePassthrough,
    RunnableBranch
)
from langchain_core.runnables.utils import Input, Output

from app.llms.dialogue import DialogueBot
from app.security.heuristics import is_malicious_prompt
from app.security.moderator import LLMModerator
from app.utils.config import BOT_MESSAGES
from app.utils.log import (
    logger, log_user_action, log_security_event, 
    log_error, log_system_event
)
from .logging_middleware import LoggingRunnable, pipeline_metrics
from .rag_pipeline import RAGPipelineStage


class TelegramBotPipeline:
    """
    Главный пайплайн обработки сообщений с использованием LangChain.
    Объединяет все этапы: безопасность, модерацию, диалог.
    """
    
    def __init__(self, dialogue_bot: DialogueBot, rag_stage: RAGPipelineStage = None):
        """
        Инициализация пайплайна
        
        Args:
            dialogue_bot: Экземпляр диалогового бота
            rag_stage: RAG этап пайплайна (если None, создается новый)
        """
        self.dialogue_bot = dialogue_bot
        self.rag_stage = rag_stage or RAGPipelineStage()
        self.stats = {
            "pipeline_requests": 0,
            "pipeline_successes": 0,
            "pipeline_errors": 0,
            "security_blocks": 0,
            "moderator_blocks": 0,
            "rag_processed": 0
        }
        
        # Создаем основной пайплайн с логированием
        self.pipeline = self._create_main_pipeline()
        self.logged_pipeline = LoggingRunnable(self.pipeline, "telegram_bot_pipeline")
        
        # Регистрируем в глобальных метриках
        pipeline_metrics.register_component("main_pipeline", self.logged_pipeline)
        
        logger.info("TelegramBotPipeline инициализирован с LangChain и логированием")
    
    def _create_main_pipeline(self):
        """Создание основного пайплайна с ветвлением"""
        return (
            # Добавляем метрики и время начала
            RunnableLambda(self._start_processing)
            # Основное ветвление логики
            | RunnableBranch(
                # Пустое сообщение
                (lambda x: self._is_empty_message(x), 
                 RunnableLambda(self._handle_empty_message)),
                
                # Эвристическая блокировка
                (lambda x: self._check_heuristics(x), 
                 RunnableLambda(self._handle_heuristic_block)),
                
                # Модерация LLM
                (lambda x: self._check_moderator(x), 
                 RunnableLambda(self._handle_moderator_block)),
                
                # RAG обработка + диалог (default)
                RunnableLambda(self._handle_rag_and_dialogue)
            )
            # Завершение обработки
            | RunnableLambda(self._finish_processing)
        )
    
    def _start_processing(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Начало обработки запроса"""
        self.stats["pipeline_requests"] += 1
        input_data["start_time"] = time.time()
        input_data["pipeline_stage"] = "started"
        
        return input_data
    
    def _is_empty_message(self, input_data: Dict[str, Any]) -> bool:
        """Проверка на пустое сообщение"""
        message = input_data.get("message", "").strip()
        return not message
    
    def _check_heuristics(self, input_data: Dict[str, Any]) -> bool:
        """Эвристическая проверка безопасности"""
        message = input_data.get("message", "")
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "unknown")
        
        is_malicious = is_malicious_prompt(message, user_id, session_id)
        input_data["heuristic_blocked"] = is_malicious
        
        return is_malicious
    
    def _check_moderator(self, input_data: Dict[str, Any]) -> bool:
        """Проверка через LLM модератор"""
        message = input_data.get("message", "")
        user_id = input_data.get("user_id", "unknown") 
        session_id = input_data.get("session_id", "unknown")
        
        try:
            verdict = self.dialogue_bot.moderator.moderate(message, user_id, session_id)
            input_data["moderator_verdict"] = verdict
            
            should_block = verdict.decision == "block"
            input_data["moderator_blocked"] = should_block
            
            return should_block
        except Exception as e:
            log_error(user_id, session_id, f"Moderator check failed: {str(e)}")
            # В случае ошибки модерации - пропускаем
            input_data["moderator_blocked"] = False
            return False
    
    def _handle_empty_message(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка пустого сообщения"""
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "unknown")
        username = input_data.get("username", "unknown")
        
        log_user_action(user_id, session_id, "empty_message", f"@{username}")
        
        return {
            **input_data,
            "response": BOT_MESSAGES["empty_message"],
            "pipeline_stage": "empty_message",
            "success": True
        }
    
    def _handle_heuristic_block(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка блокировки эвристикой"""
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "unknown")
        username = input_data.get("username", "unknown")
        
        self.dialogue_bot.stats["malicious_requests"] += 1
        self.stats["security_blocks"] += 1
        
        log_security_event(user_id, session_id, "malicious_blocked", f"@{username}")
        
        return {
            **input_data,
            "response": BOT_MESSAGES["malicious_blocked"],
            "pipeline_stage": "heuristic_block",
            "success": True
        }
    
    def _handle_moderator_block(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка блокировки модератором"""
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "unknown")
        username = input_data.get("username", "unknown")
        
        self.stats["moderator_blocks"] += 1
        
        log_security_event(user_id, session_id, "moderator_blocked", f"@{username}")
        
        return {
            **input_data,
            "response": BOT_MESSAGES["moderator_blocked"],
            "pipeline_stage": "moderator_block",
            "success": True
        }
    
    async def _handle_rag_and_dialogue(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка RAG + диалог"""
        user_id = input_data.get("user_id", "unknown")
        session_id = input_data.get("session_id", "default")
        
        try:
            # 1. RAG этап - поиск релевантной информации
            rag_result = await self.rag_stage.process(input_data)
            
            # Обновляем статистику RAG
            if rag_result.get("rag_used", False):
                self.stats["rag_processed"] += 1
            
            # 2. Диалог этап - обработка запроса с контекстом
            message = rag_result.get("enhanced_message", rag_result.get("message", ""))
            response = self.dialogue_bot.ask_gpt(message, session_id)
            
            return {
                **rag_result,
                "response": response,
                "pipeline_stage": "rag_dialogue_success",
                "success": True
            }
            
        except Exception as e:
            log_error(user_id, session_id, f"RAG + Dialogue processing failed: {str(e)}")
            
            return {
                **input_data,
                "response": BOT_MESSAGES["error"],
                "pipeline_stage": "rag_dialogue_error",
                "success": False,
                "error": str(e)
            }
    
    def _finish_processing(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Завершение обработки и сбор метрик"""
        duration = time.time() - input_data.get("start_time", time.time())
        input_data["duration"] = duration
        
        if input_data.get("success", False):
            self.stats["pipeline_successes"] += 1
        else:
            self.stats["pipeline_errors"] += 1
        
        # Логируем только ошибки или блокировки
        stage = input_data.get("pipeline_stage", "unknown")
        if stage in ["rag_dialogue_error", "heuristic_block", "moderator_block"]:
            user_id = input_data.get("user_id", "unknown")
            session_id = input_data.get("session_id", "unknown")
            log_system_event(f"pipeline_{stage}", f"Duration: {duration:.2f}s", "INFO")
        
        return input_data
    
    async def process_message(self, input_data: Dict[str, Any]) -> str:
        """
        Асинхронная обработка сообщения через пайплайн
        
        Args:
            input_data: Данные сообщения (message, user_id, session_id, username)
            
        Returns:
            str: Ответ для пользователя
        """
        try:
            result = await self.logged_pipeline.ainvoke(input_data)
            return result.get("response", BOT_MESSAGES["error"])
            
        except Exception as e:
            user_id = input_data.get("user_id", "unknown")
            session_id = input_data.get("session_id", "unknown")
            log_error(user_id, session_id, f"Pipeline failed: {str(e)}")
            self.stats["pipeline_errors"] += 1
            return BOT_MESSAGES["error"]
    
    def process_message_sync(self, input_data: Dict[str, Any]) -> str:
        """
        Синхронная обработка сообщения через пайплайн
        
        Args:
            input_data: Данные сообщения (message, user_id, session_id, username)
            
        Returns:
            str: Ответ для пользователя
        """
        try:
            result = self.logged_pipeline.invoke(input_data)
            return result.get("response", BOT_MESSAGES["error"])
            
        except Exception as e:
            user_id = input_data.get("user_id", "unknown")
            session_id = input_data.get("session_id", "unknown")
            log_error(user_id, session_id, f"Pipeline failed: {str(e)}")
            self.stats["pipeline_errors"] += 1
            return BOT_MESSAGES["error"]
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Получение статистики пайплайна"""
        total_requests = self.stats["pipeline_requests"]
        success_rate = (
            self.stats["pipeline_successes"] / total_requests
            if total_requests > 0 else 0
        )
        
        # Получаем статистику логирования
        logging_stats = self.logged_pipeline.get_stats()
        
        return {
            **self.stats,
            "success_rate": success_rate,
            "dialogue_bot_stats": self.dialogue_bot.get_stats(),
            "rag_stats": self.rag_stage.get_stats(),
            "logging_stats": logging_stats,
            "pipeline_metrics": pipeline_metrics.get_all_stats()
        }
