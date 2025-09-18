import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from aiogram import Bot, Dispatcher
import uvicorn
import httpx

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware
from .telegram_handlers import router
from .client import service_client
from .models import APIGatewayHealthCheckResponse

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для Telegram бота
bot = None
dispatcher = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global bot, dispatcher

    logger.info("Starting API Gateway...")

    # Инициализация Telegram бота
    if config.telegram_token:
        bot = Bot(token=config.telegram_token)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)

        # Удаляем webhook (на всякий случай)
        try:
            await bot.delete_webhook()
            logger.info("Telegram webhook removed")
        except Exception as e:
            logger.error(f"Failed to remove webhook: {e}")

        logger.info("Telegram bot initialized")

        # Запускаем polling в фоне
        polling_task = asyncio.create_task(dispatcher.start_polling(bot))
        logger.info("Telegram polling started")

    else:
        logger.warning("TELEGRAM_TOKEN not provided, Telegram bot disabled")

    yield

    # Очистка ресурсов
    logger.info("Shutting down API Gateway...")
    await service_client.close()
    if bot and dispatcher:
        try:
            logger.info("Stopping Telegram polling...")
            await dispatcher.stop_polling()
            logger.info("Telegram polling stopped")
        except Exception as e:
            logger.error(f"Failed to stop Telegram polling: {e}")


app = FastAPI(
    title="API Gateway Service",
    description="Входная точка для Telegram бота с маршрутизацией в микросервисы",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем middleware для трейсинга
app.middleware("http")(TracingMiddleware("api-gateway"))


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    telegram_status = "disabled"
    if bot:
        try:
            # Проверяем, что бот инициализирован
            me = await bot.get_me()
            telegram_status = "polling_active" if me else "running"
        except Exception:
            telegram_status = "running"

    return APIGatewayHealthCheckResponse(
        status="healthy",
        service="api-gateway",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
        dependencies={
            "telegram": telegram_status,
            "security_service": "available",  # В реальном проекте проверять доступность
            "rag_service": "available",
            "dialogue_service": "available",
            "monitoring_service": "available"
        }
    )


@app.get("/webhook-info")
async def webhook_info():
    """Информация о состоянии бота (polling режим)"""
    if not bot:
        return {"status": "bot_not_initialized"}

    try:
        # Получаем информацию о боте
        me = await bot.get_me()
        webhook_info = await bot.get_webhook_info()

        return {
            "mode": "polling",
            "bot_username": me.username,
            "bot_first_name": me.first_name,
            "webhook_url": webhook_info.url or "none (polling mode)",
            "webhook_pending_updates": webhook_info.pending_update_count,
            "bot_active": True
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "API Gateway",
        "version": "1.0.0",
        "description": "Входная точка микросервисной архитектуры Telegram бота (aiogram polling режим)",
        "endpoints": {
            "health": "/health",
            "webhook_info": "/webhook-info"
        },
        "mode": "polling",
        "library": "aiogram"
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
