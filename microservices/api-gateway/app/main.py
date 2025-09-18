import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import uvicorn

from .config import settings
from .telegram_handlers import (
    start_command, help_command, clear_memory_command,
    handle_message, error_handler
)
from .client import service_client
from .models import APIGatewayHealthCheckResponse

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальная переменная для Telegram приложения
telegram_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global telegram_app

    logger.info("Starting API Gateway...")

    # Инициализация Telegram бота
    if settings.telegram_token:
        telegram_app = Application.builder().token(settings.telegram_token).build()

        # Регистрация обработчиков команд
        telegram_app.add_handler(CommandHandler("start", start_command))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(CommandHandler("clear", clear_memory_command))

        # Регистрация обработчика текстовых сообщений
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Регистрация обработчика ошибок
        telegram_app.add_error_handler(error_handler)

        # Запуск polling в фоне
        asyncio.create_task(telegram_app.run_polling())

        logger.info("Telegram bot started")
    else:
        logger.warning("TELEGRAM_TOKEN not provided, Telegram bot disabled")

    yield

    # Очистка ресурсов
    logger.info("Shutting down API Gateway...")
    await service_client.close()
    if telegram_app:
        await telegram_app.shutdown()


app = FastAPI(
    title="API Gateway Service",
    description="Входная точка для Telegram бота с маршрутизацией в микросервисы",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return APIGatewayHealthCheckResponse(
        status="healthy",
        service="api-gateway",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
        dependencies={
            "telegram": "running" if telegram_app else "disabled",
            "security_service": "available",  # В реальном проекте проверять доступность
            "rag_service": "available",
            "dialogue_service": "available",
            "monitoring_service": "available"
        }
    )


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "description": "Входная точка микросервисной архитектуры Telegram бота",
        "endpoints": {
            "health": "/health"
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
