"""
Адаптер для интеграции LangChain пайплайна с Telegram обработчиками.
Преобразует Telegram данные в формат для пайплайна и обратно.
"""

from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes

from app.utils.log import logger
from .main_pipeline import TelegramBotPipeline


class TelegramAdapter:
    """
    Адаптер для интеграции LangChain пайплайна с Telegram.
    Обрабатывает преобразование данных и управляет жизненным циклом запросов.
    """
    
    def __init__(self, pipeline: TelegramBotPipeline):
        """
        Инициализация адаптера
        
        Args:
            pipeline: Экземпляр TelegramBotPipeline
        """
        self.pipeline = pipeline
        logger.info("TelegramAdapter инициализирован")
    
    def extract_message_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """
        Извлечение данных из Telegram Update в формат для пайплайна
        
        Args:
            update: Telegram Update объект
            context: Telegram Context объект
            
        Returns:
            Dict: Данные для обработки пайплайном
        """
        return {
            "message": update.message.text or "",
            "user_id": str(update.effective_user.id),
            "session_id": str(update.effective_chat.id),
            "username": update.effective_user.username or "unknown",
            "telegram_update": update,
            "telegram_context": context,
            "chat_type": update.effective_chat.type,
            "message_id": update.message.message_id
        }
    
    async def process_telegram_message(self, 
                                     update: Update, 
                                     context: ContextTypes.DEFAULT_TYPE) -> str:
        """
        Обработка Telegram сообщения через пайплайн
        
        Args:
            update: Telegram Update объект
            context: Telegram Context объект
            
        Returns:
            str: Ответ для отправки пользователю
        """
        # Извлекаем данные из Telegram
        input_data = self.extract_message_data(update, context)
        
        # Показываем статус "печатает"
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )
        except Exception as e:
            logger.warning(f"Failed to send typing action: {e}")
        
        # Обрабатываем через пайплайн
        response = await self.pipeline.process_message(input_data)
        
        return response
    
    def get_user_context(self, update: Update) -> Dict[str, str]:
        """
        Получение контекста пользователя для логирования
        
        Args:
            update: Telegram Update объект
            
        Returns:
            Dict: Контекст пользователя
        """
        return {
            "user_id": str(update.effective_user.id),
            "session_id": str(update.effective_chat.id),
            "username": update.effective_user.username or "unknown"
        }
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """
        Получение статистики адаптера и пайплайна
        
        Returns:
            Dict: Полная статистика
        """
        return {
            "adapter_version": "1.0",
            "pipeline_stats": self.pipeline.get_pipeline_stats()
        }
