import logging
import asyncio
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from common.config import config
from common.utils.tracing_middleware import log_error
from .models import TelegramMessage, SecurityCheckRequest, DialogueRequest, RAGSearchRequest, LogEntry
from .client import service_client

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def start_command(message: Message, bot: Bot):
    """Обработчик команды /start"""
    user_id = str(message.from_user.id)
    session_id = str(message.chat.id)
    username = message.from_user.username or "unknown"

    # Логируем событие
    await service_client.log_event(LogEntry(
        level="INFO",
        service="api-gateway",
        message="User started bot",
        user_id=user_id,
        session_id=session_id,
        extra={"username": username}
    ))

    await message.reply(config.bot_messages["start"])


@router.message(Command("help"))
async def help_command(message: Message, bot: Bot):
    """Обработчик команды /help"""
    user_id = str(message.from_user.id)
    session_id = str(message.chat.id)

    await service_client.log_event(LogEntry(
        level="INFO",
        service="api-gateway",
        message="User requested help",
        user_id=user_id,
        session_id=session_id
    ))

    await message.reply(config.bot_messages["help"])


@router.message(Command("clear"))
async def clear_memory_command(message: Message, bot: Bot):
    """Обработчик команды /clear"""
    user_id = str(message.from_user.id)
    session_id = str(message.chat.id)
    username = message.from_user.username or "unknown"

    try:
        # Очищаем память через Dialogue Service
        clear_response = await service_client.clear_memory(session_id, user_id)
        
        if clear_response.get("success", False):
            await service_client.log_event(LogEntry(
                level="INFO",
                service="api-gateway",
                message="User cleared memory",
                user_id=user_id,
                session_id=session_id,
                extra={
                    "username": username,
                    "messages_cleared": clear_response.get("messages_cleared", 0)
                }
            ))

            await message.reply(f"✅ Память очищена! Удалено сообщений: {clear_response.get('messages_cleared', 0)}")
        else:
            await message.reply("❌ Ошибка при очистке памяти. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Clear memory error: {e}")
        
        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="api-gateway",
            error_type=type(e).__name__,
            error_message=f"Clear memory command failed: {str(e)}",
            user_id=user_id,
            session_id=session_id,
            context={
                "operation": "clear_memory_command",
                "username": username,
                "command": "/clear"
            }
        )
        
        await message.reply("❌ Ошибка при очистке памяти. Попробуйте позже.")


@router.message(Command("history"))
async def history_command(message: Message, bot: Bot):
    """Обработчик команды /history"""
    user_id = str(message.from_user.id)
    session_id = str(message.chat.id)
    username = message.from_user.username or "unknown"

    try:
        # Получаем историю диалога
        history_response = await service_client.get_dialogue_history(session_id, limit=10)
        
        if history_response.get("count", 0) == 0:
            await message.reply("📝 История диалога пуста.")
            return

        # Формируем сообщение с историей
        history_text = "📝 **Последние сообщения:**\n\n"
        
        for i, msg in enumerate(history_response.get("history", [])[-10:], 1):
            role_emoji = "👤" if msg.get("role") == "user" else "🤖"
            content = msg.get("content", "")[:100]  # Ограничиваем длину
            if len(msg.get("content", "")) > 100:
                content += "..."
            
            history_text += f"{i}. {role_emoji} {content}\n"

        # Добавляем информацию о trace_id последнего сообщения
        last_message = history_response.get("history", [])[-1] if history_response.get("history") else None
        if last_message and last_message.get("trace_id"):
            history_text += f"\n🔍 **Trace ID:** `{last_message['trace_id']}`"

        await service_client.log_event(LogEntry(
            level="INFO",
            service="api-gateway",
            message="User requested history",
            user_id=user_id,
            session_id=session_id,
            extra={
                "username": username,
                "history_count": history_response.get("count", 0)
            }
        ))

        await message.reply(history_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"History command error: {e}")
        
        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="api-gateway",
            error_type=type(e).__name__,
            error_message=f"History command failed: {str(e)}",
            user_id=user_id,
            session_id=session_id,
            context={
                "operation": "history_command",
                "username": username,
                "command": "/history"
            }
        )
        
        await message.reply("❌ Ошибка при получении истории. Попробуйте позже.")


@router.message()
async def handle_message(message: Message, bot: Bot):
    """Обработка текстовых сообщений"""
    try:
        user_id = str(message.from_user.id)
        session_id = str(message.chat.id)
        username = message.from_user.username or "unknown"
        message_text = message.text.strip()

        if not message_text:
            await message.reply(config.bot_messages["empty_message"])
            return

        # 1. Параллельно выполняем проверку безопасности и RAG поиск (оптимизация для serverless)
        security_request = SecurityCheckRequest(
            message=message_text,
            user_id=user_id,
            session_id=session_id
        )

        rag_request = RAGSearchRequest(
            query=message_text,
            user_id=user_id,
            session_id=session_id
        )

        # Выполняем security и RAG параллельно для ускорения
        security_task = service_client.check_security(security_request)
        rag_task = service_client.search_rag(rag_request)

        security_response, rag_response = await asyncio.gather(
            security_task, rag_task, return_exceptions=True
        )

        # Обрабатываем ошибки от параллельных запросов
        if isinstance(security_response, Exception):
            logger.error(f"Security check failed: {security_response}")
            # Fallback: разрешаем запрос если security недоступен
            from common.models import SecurityCheckResponse
            security_response = SecurityCheckResponse(allowed=True, reason="Security service unavailable")

        if isinstance(rag_response, Exception):
            logger.error(f"RAG search failed: {rag_response}")
            # Fallback: пустой контекст если RAG недоступен
            from common.models import RAGSearchResponse
            rag_response = RAGSearchResponse(
                context="", documents_found=0, search_time=0.0,
                documents_info=[], similarity_scores=[], error=str(rag_response)
            )

        # Проверяем результат безопасности
        if not security_response.allowed:
            await service_client.log_event(LogEntry(
                level="WARNING",
                service="api-gateway",
                message="Message blocked by security",
                user_id=user_id,
                session_id=session_id,
                extra={
                    "reason": security_response.reason,
                    "category": security_response.category
                }
            ))

            if security_response.category in ["malware", "hate", "self-harm", "sexual", "jailbreak"]:
                await message.reply(config.bot_messages["malicious_blocked"])
            else:
                await message.reply(config.bot_messages["moderator_blocked"])
            return

        # 2. Обрабатываем диалог с контекстом
        dialogue_request = DialogueRequest(
            message=message_text,
            user_id=user_id,
            session_id=session_id,
            context={
                "rag_context": rag_response.context,
                "documents_found": rag_response.documents_found
            }
        )

        dialogue_response = await service_client.process_dialogue(dialogue_request)

        # 3. Отправляем ответ пользователю
        await message.reply(dialogue_response.response)

        # 4. Логируем успешную обработку
        await service_client.log_event(LogEntry(
            level="INFO",
            service="api-gateway",
            message="Message processed successfully",
            user_id=user_id,
            session_id=session_id,
            extra={
                "response_length": len(dialogue_response.response),
                "documents_found": rag_response.documents_found,
                "search_time": rag_response.search_time
            }
        ))

    except Exception as e:
        logger.error(f"Message handling error: {e}")

        # Логируем ошибку
        await service_client.log_event(LogEntry(
            level="ERROR",
            service="api-gateway",
            message=f"Message processing failed: {str(e)}",
            user_id=str(message.from_user.id) if message.from_user else "unknown",
            session_id=str(message.chat.id) if message.chat else "unknown"
        ))

        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="api-gateway",
            error_type=type(e).__name__,
            error_message=f"Message processing failed: {str(e)}",
            user_id=str(message.from_user.id) if message.from_user else "unknown",
            session_id=str(message.chat.id) if message.chat else "unknown",
            context={
                "operation": "handle_message",
                "message_length": len(message.text) if message.text else 0,
                "username": message.from_user.username if message.from_user else "unknown"
            }
        )

        await message.reply(config.bot_messages["error"])


@router.errors()
async def error_handler(exception: Exception, update: Message = None):
    """Обработчик ошибок Telegram"""
    user_id = str(update.from_user.id) if update and update.from_user else "unknown"
    session_id = str(update.chat.id) if update and update.chat else "unknown"

    await service_client.log_event(LogEntry(
        level="ERROR",
        service="api-gateway",
        message=f"Telegram error: {str(exception)}",
        user_id=user_id,
        session_id=session_id
    ))

    # Отправляем детальную информацию об ошибке в monitoring-service
    log_error(
        service="api-gateway",
        error_type=type(exception).__name__,
        error_message=f"Telegram error: {str(exception)}",
        user_id=user_id,
        session_id=session_id,
        context={
            "operation": "telegram_error_handler",
            "update_type": type(update).__name__ if update else "unknown",
            "has_message": hasattr(update, 'message') if update else False
        }
    )

    if update:
        await update.reply(config.bot_messages["telegram_error"])
