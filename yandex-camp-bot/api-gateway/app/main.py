import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException, Request, status
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware, log_error
from common.utils import BaseService
from .telegram_handlers import router
from .client import service_client
from .models import APIGatewayHealthCheckResponse

# Глобальные переменные для Telegram бота
bot = None
dispatcher = None


class APIGatewayService(BaseService):
    """API Gateway Service с использованием базового класса"""

    def __init__(self):
        super().__init__(
            service_name="api-gateway",
            version="1.0.0",
            description="Входная точка для Telegram бота с маршрутизацией в микросервисы",
            dependencies={
                "telegram": "available",
                "security_service": "available",
                "rag_service": "available",
                "dialogue_service": "available",
                "monitoring_service": "available"
            }
        )

    async def on_startup(self):
        """Инициализация Telegram бота с вебхуком"""
        global bot, dispatcher

        # Инициализация Telegram бота
        if config.telegram_token:
            bot = Bot(token=config.telegram_token)
            dispatcher = Dispatcher()
            dispatcher.include_router(router)

            # Устанавливаем webhook
            webhook_url = config.webhook_url
            try:
                await bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True
                )
                self.logger.info(f"Telegram webhook set to: {webhook_url}")
                
                # Получаем информацию о вебхуке для логирования
                webhook_info = await bot.get_webhook_info()
                self.logger.info(f"Webhook info: {webhook_info}")
                
            except Exception as e:
                self.logger.error(f"Failed to set webhook: {e}")
                self.handle_error_response(
                    error=e,
                    context={"operation": "webhook_setup", "bot_initialized": True}
                )
                raise

            self.logger.info("Telegram bot initialized in webhook mode")

        else:
            self.logger.warning("TELEGRAM_TOKEN not provided, Telegram bot disabled")

    async def on_shutdown(self):
        """Очистка ресурсов"""
        await service_client.close()
        if bot:
            try:
                self.logger.info("Removing Telegram webhook...")
                await bot.delete_webhook()
                self.logger.info("Telegram webhook removed")
            except Exception as e:
                self.logger.error(f"Failed to remove webhook: {e}")
                self.handle_error_response(
                    error=e,
                    context={"operation": "webhook_removal", "bot_initialized": True}
                )

    async def check_dependencies(self):
        """Проверка зависимостей API Gateway"""
        dependencies_status = {}

        # Проверяем Telegram бота
        if bot:
            try:
                me = await bot.get_me()
                dependencies_status["telegram"] = "webhook_active" if me else "running"
            except Exception:
                dependencies_status["telegram"] = "running"
        else:
            dependencies_status["telegram"] = "disabled"

        # Остальные сервисы пока считаем доступными
        dependencies_status.update({
            "security_service": "available",
            "rag_service": "available",
            "dialogue_service": "available",
            "monitoring_service": "available"
        })

        return dependencies_status

    def create_health_response(self, status: str, service_status: str = None, additional_stats: dict = None):
        """Создание health check ответа для API Gateway"""
        telegram_status = "disabled"
        if bot:
            try:
                telegram_status = "webhook_active"
            except Exception:
                telegram_status = "running"

        return APIGatewayHealthCheckResponse(
            status=status,
            service=self.service_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            dependencies={
                "telegram": telegram_status,
                "security_service": "available",
                "rag_service": "available",
                "dialogue_service": "available",
                "monitoring_service": "available"
            }
        )


# Создаем экземпляр сервиса
service = APIGatewayService()
app = service.app


@app.post("/webhook")
async def webhook_handler(request: Request):
    """Обработчик вебхуков от Telegram"""
    if not bot or not dispatcher:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bot not initialized"
        )
    
    try:
        # Парсим обновление от Telegram
        update_data = await request.json()
        update = Update(**update_data)
        
        # Обрабатываем обновление
        await dispatcher.feed_update(bot, update)
        
        return {"status": "ok"}
    except Exception as e:
        service.logger.error(f"Webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing update: {e}"
        )


@app.get("/webhook-info")
async def webhook_info():
    """Информация о состоянии вебхука"""
    if not bot:
        return {"status": "bot_not_initialized"}

    try:
        # Получаем информацию о боте и вебхуке
        me = await bot.get_me()
        webhook_info = await bot.get_webhook_info()

        return {
            "mode": "webhook",
            "bot_username": me.username,
            "bot_first_name": me.first_name,
            "webhook_url": webhook_info.url or "none",
            "webhook_pending_updates": webhook_info.pending_update_count,
            "webhook_active": webhook_info.url is not None,
            "bot_active": True
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )