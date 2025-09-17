from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.utils.config import TELEGRAM_TOKEN, OPENAI_API_KEY, FOLDER_ID
from app.handlers import (
    start, clear_memory, help_command, stats_command,
    handle_message, error_handler
)
from app.utils.log import logger, log_system_event


def main():
    """Основная функция"""
    try:
        log_system_event("bot_startup_started", "Starting bot initialization")
        
        # Проверяем переменные окружения
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN not found in environment variables")
        if not OPENAI_API_KEY:
            raise ValueError("YC_OPENAI_TOKEN not found in environment variables")
        if not FOLDER_ID:
            raise ValueError("YC_FOLDER_ID not found in environment variables")
        
        log_system_event("environment_check_passed", "All required environment variables found")
        
        # Проверяем инициализацию LangChain
        logger.info("LangChain with YandexGPT initialized successfully")

        application = Application.builder().token(TELEGRAM_TOKEN).build()
        log_system_event("telegram_application_created", "Telegram application created successfully")

        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear_memory))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))

        # Регистрируем обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Регистрируем обработчик ошибок
        application.add_error_handler(error_handler)
        
        log_system_event("handlers_registered", "All command and message handlers registered")
        logger.info("Бот с LangChain запускается...")
        
        log_system_event("bot_startup_completed", "Bot startup completed successfully")
        application.run_polling()

    except Exception as e:
        log_system_event("bot_startup_failed", f"Failed to start bot: {str(e)}", "ERROR")
        logger.error(f"Failed to start bot: {str(e)}")
        raise


if __name__ == "__main__":
    main()