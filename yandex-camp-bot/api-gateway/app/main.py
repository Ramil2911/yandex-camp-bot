import logging
import asyncio
import time
from fastapi import FastAPI, HTTPException, Request
from aiogram import Bot, Dispatcher

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
        """Инициализация Telegram бота"""
        global bot, dispatcher

        # Инициализация Telegram бота
        if config.telegram_token:
            bot = Bot(token=config.telegram_token)
            dispatcher = Dispatcher()
            dispatcher.include_router(router)

            # Удаляем webhook (на всякий случай)
            try:
                await bot.delete_webhook()
                self.logger.info("Telegram webhook removed")
            except Exception as e:
                self.logger.error(f"Failed to remove webhook: {e}")
                self.handle_error_response(
                    error=e,
                    context={"operation": "webhook_cleanup", "bot_initialized": True}
                )

            self.logger.info("Telegram bot initialized")

            # Запускаем polling в фоне
            polling_task = asyncio.create_task(dispatcher.start_polling(bot))
            self.logger.info("Telegram polling started")

        else:
            self.logger.warning("TELEGRAM_TOKEN not provided, Telegram bot disabled")

    async def on_shutdown(self):
        """Очистка ресурсов"""
        await service_client.close()
        if bot and dispatcher:
            try:
                self.logger.info("Stopping Telegram polling...")
                await dispatcher.stop_polling()
                self.logger.info("Telegram polling stopped")
            except Exception as e:
                self.logger.error(f"Failed to stop Telegram polling: {e}")
                self.handle_error_response(
                    error=e,
                    context={"operation": "polling_shutdown", "bot_initialized": True}
                )

    async def check_dependencies(self):
        """Проверка зависимостей API Gateway"""
        dependencies_status = {}

        # Проверяем Telegram бота
        if bot:
            try:
                me = await bot.get_me()
                dependencies_status["telegram"] = "polling_active" if me else "running"
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
                # Проверяем, что бот инициализирован
                # В асинхронном контексте мы не можем вызвать bot.get_me() синхронно
                telegram_status = "polling_active"
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




if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
