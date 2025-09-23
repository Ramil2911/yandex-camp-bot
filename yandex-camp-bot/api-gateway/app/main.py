import logging
import asyncio
import time
import json
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware, log_error
from common.utils import BaseService
from .telegram_handlers import router
from .client import service_client
from .models import APIGatewayHealthCheckResponse, LogEntry, ServiceAccount, ServiceMetrics

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

        # Инициализация словаря сервисных аккаунтов
        self.service_accounts = {}  # account_id -> ServiceAccount

        # Инициализация Telegram бота (атрибуты экземпляра для лучшей инкапсуляции)
        self.bot = None
        self.dispatcher = None

    async def on_startup(self):
        """Инициализация Telegram бота"""
        global bot, dispatcher

        # Инициализация Telegram бота
        if config.telegram_token:
            self.bot = Bot(token=config.telegram_token)
            self.dispatcher = Dispatcher()
            self.dispatcher.include_router(router)

            # Синхронизируем с глобальными переменными для совместимости
            bot = self.bot
            dispatcher = self.dispatcher

            self.logger.info("Telegram bot initialized")

            # Логируем выбранный режим работы бота
            self.logger.info(f"Выбран режим работы бота: {config.bot_mode}")

            # Выбираем режим работы бота
            if config.bot_mode.lower() == "webhook":
                self.logger.info("Инициализация режима webhook для Telegram бота")
                await self._setup_webhook_mode()
            elif config.bot_mode.lower() == "polling":
                self.logger.info("Инициализация режима polling для Telegram бота")
                await self._setup_polling_mode()
            else:
                self.logger.error(f"Invalid BOT_MODE: {config.bot_mode}. Supported modes: polling, webhook")
                return

        else:
            self.logger.warning("TELEGRAM_TOKEN not provided, Telegram bot disabled")

        # Инициализация сервисных аккаунтов
        await self._init_service_accounts()

    async def _init_service_accounts(self):
        """
        Инициализация сервисных аккаунтов из конфигурации.

        Сервисные аккаунты настраиваются ТОЛЬКО через переменные окружения
        и не могут быть изменены во время выполнения.

        Переменные окружения:
        - SERVICE_ACCOUNTS_ENABLED=true/false - включить/выключить сервисные аккаунты
        - SERVICE_ACCOUNT_IDS=123456789,987654321 - список Telegram user_id через запятую

        Пример:
        SERVICE_ACCOUNTS_ENABLED=true
        SERVICE_ACCOUNT_IDS=123456789,987654321
        """
        from datetime import datetime

        # Проверяем, включены ли сервисные аккаунты
        if not config.service_accounts_enabled:
            self.logger.info("Service accounts are disabled")
            return

        # Получаем список user_id сервисных аккаунтов из конфигурации
        if not config.service_account_ids:
            self.logger.info("No service account IDs configured")
            return

        try:
            # Формат: "123456789,987654321,555666777" (список Telegram user_id)
            account_ids = [id.strip() for id in config.service_account_ids.split(",") if id.strip()]

            for account_id in account_ids:
                # Валидация: user_id должен быть числом (Telegram ID)
                if not account_id.isdigit():
                    self.logger.warning(f"Invalid service account ID (must be numeric): {account_id}")
                    continue

                account = ServiceAccount(
                    account_id=account_id,
                    name=f"Service Account {account_id}",
                    description=f"Сервисный аккаунт для мониторинга метрик (ID: {account_id})",
                    enabled=True,
                    created_at=datetime.utcnow()
                )
                self.service_accounts[account_id] = account
                self.logger.info(f"Initialized service account: {account_id}")

            # Подсчитываем успешно инициализированные аккаунты
            enabled_accounts = len([a for a in self.service_accounts.values() if a.enabled])
            if enabled_accounts > 0:
                self.logger.info(f"Successfully initialized {enabled_accounts} service accounts")
            else:
                self.logger.warning("No service accounts were initialized - check SERVICE_ACCOUNT_IDS format")

        except Exception as e:
            self.logger.error(f"Failed to initialize service accounts: {e}")

    async def _setup_webhook_mode(self):
        """Настройка режима webhook"""
        if not config.webhook_url:
            self.logger.error("WEBHOOK_URL not provided, cannot setup webhook mode")
            return

        try:
            # Устанавливаем webhook
            webhook_full_url = f"{config.webhook_url.rstrip('/')}{config.webhook_path}"
            await bot.set_webhook(
                url=webhook_full_url,
                drop_pending_updates=True
            )

            # Проверяем установку webhook
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url == webhook_full_url:
                self.logger.info(f"Webhook successfully set to: {webhook_full_url}")
            else:
                self.logger.error(f"Webhook setup failed. Expected: {webhook_full_url}, Got: {webhook_info.url}")

        except Exception as e:
            self.logger.error(f"Failed to setup webhook: {e}")
            self.handle_error_response(
                error=e,
                context={"operation": "webhook_setup", "webhook_url": config.webhook_url}
            )

    async def _setup_polling_mode(self):
        """Настройка режима polling"""
        try:
            # Удаляем webhook (на всякий случай)
            await bot.delete_webhook()
            self.logger.info("Webhook removed for polling mode")

            # Запускаем polling в фоне
            polling_task = asyncio.create_task(dispatcher.start_polling(bot))
            self.logger.info("Telegram polling started")

        except Exception as e:
            self.logger.error(f"Failed to setup polling: {e}")
            self.handle_error_response(
                error=e,
                context={"operation": "polling_setup"}
            )

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

    def get_service_accounts(self):
        """Получить все сервисные аккаунты (только для чтения)"""
        return list(self.service_accounts.values())

    async def send_metrics_to_service_accounts(self, metrics: ServiceMetrics):
        """Отправить метрики сервисным аккаунтам"""
        if not self.bot:
            self.logger.warning("Bot not initialized, cannot send metrics to service accounts")
            return

        # Проверяем, есть ли активные сервисные аккаунты
        active_accounts = [acc for acc in self.service_accounts.values() if acc.enabled]
        if not active_accounts:
            self.logger.debug("No active service accounts configured")
            return

        message_parts = [
            "🤖 **[SERVICE METRICS]**\n",  # Маркер для идентификации сообщений метрик
            "📊 **Метрики обработки запроса**\n",
            f"🆔 Request ID: `{metrics.request_id}`\n",
            f"👤 User ID: `{metrics.user_id or 'unknown'}`\n",
            f"💬 Session ID: `{metrics.session_id or 'unknown'}`\n",
            f"⏱️ Общее время: `{metrics.total_time:.2f} сек`\n",
            f"📈 Статус: `{metrics.status}`\n\n",
            "**Время по сервисам:**\n"
        ]

        # Для сервисных аккаунтов добавляем дополнительную информацию
        if active_accounts:  # Если есть активные сервисные аккаунты
            message_parts.append("\n💡 *Как сервисный аккаунт вы можете:*\n")
            message_parts.append("• Отправлять тестовые сообщения боту\n")
            message_parts.append("• Получать детальные метрики обработки\n")
            message_parts.append("• Тестировать функциональность системы\n")

        for service_name, duration in metrics.services_timing.items():
            message_parts.append(f"🔹 {service_name}: `{duration:.2f} сек`\n")

        message = "".join(message_parts)

        # Отправляем сообщение всем активным сервисным аккаунтам
        sent_count = 0
        failed_count = 0
        for account in active_accounts:
            try:
                await self.bot.send_message(
                    chat_id=int(account.account_id),
                    text=message,
                    parse_mode="Markdown"
                )
                sent_count += 1
                self.logger.debug(f"Metrics sent to service account {account.account_id}")
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Failed to send metrics to service account {account.account_id}: {e}")

        self.logger.info(f"Metrics sent to {sent_count} service accounts, {failed_count} failed")


# Создаем экземпляр сервиса
service = APIGatewayService()
app = service.app




@app.post("/webhook")
async def webhook_handler(request: Request):
    """Обработчик webhook от Telegram"""
    if not bot or not dispatcher:
        service.logger.error("Webhook received but bot not initialized")
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Извлекаем информацию для логирования
    user_id = None
    session_id = None
    update_type = "unknown"

    try:
        # Получаем данные от Telegram
        update_data = await request.json()
        service.logger.info(f"Webhook received: {len(update_data)} bytes")

        # Создаем Update объект из данных
        from aiogram.types import Update
        update = Update(**update_data)

        # Определяем тип обновления и извлекаем информацию о пользователе
        if update.message:
            update_type = "message"
            user_id = str(update.message.from_user.id) if update.message.from_user else None
            session_id = str(update.message.chat.id) if update.message.chat else None

            # Проверяем на специальные случаи для игнорирования
            if user_id:
                # Игнорируем сообщения от самого бота
                try:
                    me = await bot.get_me()
                    if me and str(me.id) == user_id:
                        service.logger.info(f"Ignoring webhook from bot itself: {user_id}")
                        return {"status": "ignored", "reason": "bot_itself"}
                except Exception:
                    pass  # Игнорируем ошибки при получении информации о боте

                # NOTE: Сервисные аккаунты теперь МОГУТ отправлять сообщения для тестирования
        elif update.callback_query:
            update_type = "callback_query"
            user_id = str(update.callback_query.from_user.id) if update.callback_query.from_user else None
            session_id = str(update.callback_query.message.chat.id) if update.callback_query.message and update.callback_query.message.chat else None
        elif update.inline_query:
            update_type = "inline_query"
            user_id = str(update.inline_query.from_user.id) if update.inline_query.from_user else None
        elif update.chosen_inline_result:
            update_type = "chosen_inline_result"
            user_id = str(update.chosen_inline_result.from_user.id) if update.chosen_inline_result.from_user else None

        # Логируем получение обновления
        await service_client.log_event(LogEntry(
            level="INFO",
            service="api-gateway",
            message=f"Webhook update received: {update_type}",
            user_id=user_id or "unknown",
            session_id=session_id or "unknown",
            extra={
                "update_type": update_type,
                "update_id": update.update_id,
                "has_message": update.message is not None,
                "has_callback_query": update.callback_query is not None,
                "has_inline_query": update.inline_query is not None
            }
        ))

        # Обрабатываем update через dispatcher
        await dispatcher.feed_update(bot=bot, update=update)

        # Логируем успешную обработку
        service.logger.info(f"Webhook update processed successfully: {update_type}")
        await service_client.log_event(LogEntry(
            level="INFO",
            service="api-gateway",
            message=f"Webhook update processed: {update_type}",
            user_id=user_id or "unknown",
            session_id=session_id or "unknown",
            extra={
                "update_type": update_type,
                "update_id": update.update_id,
                "processing_status": "success"
            }
        ))

        return JSONResponse(content={"status": "ok"}, status_code=200)

    except json.JSONDecodeError as e:
        service.logger.error(f"Webhook JSON decode error: {e}")
        await service_client.log_event(LogEntry(
            level="ERROR",
            service="api-gateway",
            message="Webhook JSON decode error",
            user_id=user_id or "unknown",
            session_id=session_id or "unknown",
            extra={
                "error_type": "json_decode",
                "error_message": str(e)
            }
        ))
        raise HTTPException(status_code=400, detail="Invalid JSON")

    except Exception as e:
        service.logger.error(f"Webhook processing error: {e}")
        await service_client.log_event(LogEntry(
            level="ERROR",
            service="api-gateway",
            message=f"Webhook processing failed: {str(e)}",
            user_id=user_id or "unknown",
            session_id=session_id or "unknown",
            extra={
                "update_type": update_type,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        ))

        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="api-gateway",
            error_type=type(e).__name__,
            error_message=f"Webhook processing failed: {str(e)}",
            user_id=user_id or "unknown",
            session_id=session_id or "unknown",
            context={
                "operation": "webhook_handler",
                "update_type": update_type,
                "update_data_size": len(str(update_data)) if 'update_data' in locals() else 0
            }
        )

        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/webhook-info")
async def webhook_info():
    """Информация о состоянии бота"""
    if not bot:
        return {"status": "bot_not_initialized"}

    try:
        # Получаем информацию о боте
        me = await bot.get_me()
        webhook_info = await bot.get_webhook_info()

        return {
            "mode": config.bot_mode,
            "bot_username": me.username,
            "bot_first_name": me.first_name,
            "webhook_url": webhook_info.url or "none (polling mode)",
            "webhook_pending_updates": webhook_info.pending_update_count,
            "bot_active": True
        }
    except Exception as e:
        return {"error": str(e)}


# API для приема метрик от сервисов
@app.post("/service-metrics")
async def receive_service_metrics(metrics: ServiceMetrics):
    """Получить метрики от сервисов и отправить сервисным аккаунтам"""
    # Этот endpoint не требует аутентификации, так как вызывается внутренними сервисами
    await service.send_metrics_to_service_accounts(metrics)
    return {"message": "Metrics sent to service accounts"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
