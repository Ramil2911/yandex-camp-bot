from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio

from app.utils.config import TELEGRAM_TOKEN, OPENAI_API_KEY, FOLDER_ID
from app.handlers import (
    start, clear_memory, help_command, stats_command, rag_command,
    handle_message, error_handler, initialize_rag_system
)
from app.utils.log import logger, log_bot_startup, log_config_info, log_error, log_system_event


async def initialize_bot_components():
    """Инициализация компонентов бота при старте"""
    log_bot_startup("rag_init", "Initializing RAG system...")
    try:
        await initialize_rag_system()
        log_bot_startup("rag_init", "RAG system initialized successfully")
    except Exception as e:
        log_error("system", "rag_init", f"RAG initialization failed: {str(e)}")
        logger.warning("RAG система не инициализирована, бот будет работать без RAG")
        # Не прерываем запуск бота, если RAG не инициализировался


def main():
    """Основная функция"""
    try:
        log_bot_startup("initialization", "Starting YandexGPT Telegram Bot")

        # Проверяем переменные окружения
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN not found in environment variables")
        if not OPENAI_API_KEY:
            raise ValueError("YC_OPENAI_TOKEN not found in environment variables")
        if not FOLDER_ID:
            raise ValueError("YC_FOLDER_ID not found in environment variables")

        # Логируем конфигурацию
        log_config_info("TELEGRAM_BOT", "configured", "env")
        log_config_info("YANDEX_GPT", "configured", "env")
        log_config_info("YANDEX_FOLDER", f"folder_{FOLDER_ID[:8]}...", "env")

        # Инициализируем компоненты бота
        log_bot_startup("components_init", "Initializing bot components")
        asyncio.run(initialize_bot_components())

        log_bot_startup("telegram_app", "Creating Telegram application")
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Регистрируем обработчики команд
        log_bot_startup("handlers", "Registering command handlers")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear_memory))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("rag", rag_command))

        # Регистрируем обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Регистрируем обработчик ошибок
        application.add_error_handler(error_handler)

        log_bot_startup("startup_complete", "All handlers registered, starting polling")
        logger.info("🤖 YandexGPT Telegram Bot started successfully")
        application.run_polling()

    except Exception as e:
        log_error("system", "system", f"Bot startup failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()