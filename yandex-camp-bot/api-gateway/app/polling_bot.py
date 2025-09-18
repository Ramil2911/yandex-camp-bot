#!/usr/bin/env python3
"""
Отдельный скрипт для polling Telegram бота.
Запускается в отдельном процессе от основного API сервера.
"""

import logging
import asyncio
import sys
import os

# Добавляем путь к модулям
sys.path.append('/app')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from common.config import config
from .telegram_handlers import (
    start_command, help_command, clear_memory_command,
    handle_message, error_handler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция для запуска polling бота"""
    if not config.telegram_token:
        logger.error("TELEGRAM_TOKEN not provided")
        return

    logger.info("Starting Telegram polling bot...")

    # Создаем приложение
    application = Application.builder().token(config.telegram_token).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_memory_command))

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)

    # Удаляем webhook перед запуском polling
    await application.bot.delete_webhook()
    logger.info("Webhook removed, starting polling...")

    # Запускаем polling
    try:
        await application.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Polling error: {e}")
    finally:
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
