import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from common.config import config
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

    # Очищаем память в Dialogue Service
    try:
        dialogue_request = DialogueRequest(
            message="CLEAR_MEMORY",
            user_id=user_id,
            session_id=session_id
        )
        await service_client.process_dialogue(dialogue_request)

        await service_client.log_event(LogEntry(
            level="INFO",
            service="api-gateway",
            message="User cleared memory",
            user_id=user_id,
            session_id=session_id,
            extra={"username": username}
        ))

        await message.reply(config.bot_messages["memory_cleared"])

    except Exception as e:
        logger.error(f"Clear memory error: {e}")
        await message.reply(config.bot_messages["error"])


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

        # 1. Проверяем безопасность
        security_request = SecurityCheckRequest(
            message=message_text,
            user_id=user_id,
            session_id=session_id
        )

        security_response = await service_client.check_security(security_request)

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

        # 2. Ищем релевантный контекст в RAG
        rag_request = RAGSearchRequest(
            query=message_text,
            user_id=user_id,
            session_id=session_id
        )

        rag_response = await service_client.search_rag(rag_request)

        # 3. Обрабатываем диалог с контекстом
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

        # 4. Отправляем ответ пользователю
        await message.reply(dialogue_response.response)

        # 5. Логируем успешную обработку
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

    if update:
        await update.reply(config.bot_messages["telegram_error"])
