import logging
from telegram import Update
from telegram.ext import ContextTypes
from .config import settings
from .models import TelegramMessage, SecurityCheckRequest, DialogueRequest, RAGSearchRequest, LogEntry
from .client import service_client

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    # Логируем событие
    await service_client.log_event(LogEntry(
        level="INFO",
        service="api-gateway",
        message="User started bot",
        user_id=user_id,
        session_id=session_id,
        extra={"username": username}
    ))

    await update.message.reply_text(settings.bot_messages["start"])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)

    await service_client.log_event(LogEntry(
        level="INFO",
        service="api-gateway",
        message="User requested help",
        user_id=user_id,
        session_id=session_id
    ))

    await update.message.reply_text(settings.bot_messages["help"])


async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

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

        await update.message.reply_text(settings.bot_messages["memory_cleared"])

    except Exception as e:
        logger.error(f"Clear memory error: {e}")
        await update.message.reply_text(settings.bot_messages["error"])


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    try:
        user_id = str(update.effective_user.id)
        session_id = str(update.effective_chat.id)
        username = update.effective_user.username or "unknown"
        message_text = update.message.text.strip()

        if not message_text:
            await update.message.reply_text(settings.bot_messages["empty_message"])
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
                await update.message.reply_text(settings.bot_messages["malicious_blocked"])
            else:
                await update.message.reply_text(settings.bot_messages["moderator_blocked"])
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
        await update.message.reply_text(dialogue_response.response)

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
            user_id=str(update.effective_user.id) if update.effective_user else "unknown",
            session_id=str(update.effective_chat.id) if update.effective_chat else "unknown"
        ))

        await update.message.reply_text(settings.bot_messages["error"])


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок Telegram"""
    user_id = str(update.effective_user.id) if update and update.effective_user else "unknown"
    session_id = str(update.effective_chat.id) if update and update.effective_chat else "unknown"

    await service_client.log_event(LogEntry(
        level="ERROR",
        service="api-gateway",
        message=f"Telegram error: {str(context.error)}",
        user_id=user_id,
        session_id=session_id
    ))

    if update and update.effective_message:
        await update.effective_message.reply_text(settings.bot_messages["telegram_error"])
