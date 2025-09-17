from telegram import Update
from telegram.ext import ContextTypes

from app.utils.config import BOT_MESSAGES
from app.llms import dialogue_bot
from app.utils.log import logger, log_user_action, log_security_event, log_system_event
from app.security.heuristics import is_malicious_prompt


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(
        user_id=user_id,
        session_id=chat_id,
        action="start_command",
        details=f"User: @{username}, Chat: {chat_id}"
    )

    logger.info(f"User @{username} ({user_id}) started bot in chat {chat_id}")

    await update.message.reply_text(BOT_MESSAGES["start"])


async def clear_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка памяти разговора"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(
        user_id=user_id,
        session_id=session_id,
        action="clear_memory_command",
        details=f"User: @{username}"
    )

    dialogue_bot.clear_memory(session_id)
    await update.message.reply_text(BOT_MESSAGES["memory_cleared"])

    logger.info(f"User @{username} ({user_id}) cleared memory for session {session_id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(
        user_id=user_id,
        session_id=session_id,
        action="help_command",
        details=f"User: @{username}"
    )

    await update.message.reply_text(BOT_MESSAGES["help"])

    logger.info(f"User @{username} ({user_id}) requested help in session {session_id}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику бота"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(
        user_id=user_id,
        session_id=session_id,
        action="stats_command",
        details=f"User: @{username}"
    )

    stats = dialogue_bot.get_stats()

    stats_text = f"""
📊 **Статистика бота**

📈 **Общая статистика:**
• Всего запросов: {stats['total_requests']}
• Успешных: {stats['successful_requests']}
• Неудачных: {stats['failed_requests']}
• Подозрительных: {stats['malicious_requests']}

⏱️ **Производительность:**
• Среднее время ответа: {stats['average_response_time']:.2f}с
• Успешность: {stats['success_rate']:.1%}

👥 **Сессии:**
• Активных сессий: {stats['active_sessions']}
    """

    await update.message.reply_text(stats_text)
    logger.info(f"User @{username} ({user_id}) requested stats in session {session_id}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_message = update.message.text
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(
        user_id=user_id,
        session_id=session_id,
        action="message_received",
        details=f"User: @{username}, Message length: {len(user_message)} chars"
    )

    logger.info(f"User @{username} ({user_id}) sent message in session {session_id}: {user_message[:100]}...")

    if not user_message.strip():
        log_user_action(
            user_id=user_id,
            session_id=session_id,
            action="empty_message_rejected",
            details="User sent empty message"
        )
        await update.message.reply_text(BOT_MESSAGES["empty_message"])
        return

    try:
        # Показываем статус "печатает"
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        # Проверка на вредоносные промпты
        if is_malicious_prompt(user_message, user_id, session_id):
            dialogue_bot.stats["malicious_requests"] += 1

            log_security_event(
                user_id=user_id,
                session_id=session_id,
                event="malicious_prompt_detected",
                details=f"User: @{username}, Message: {user_message[:200]}...",
                severity="WARNING"
            )

            log_user_action(
                user_id=user_id,
                session_id=session_id,
                action="malicious_message_blocked",
                details=f"Message blocked: {user_message[:100]}...",
                level="WARNING"
            )

            logger.warning(f"Malicious prompt detected from user @{username} ({user_id}): {user_message[:100]}...")
            await update.message.reply_text(BOT_MESSAGES["malicious_blocked"])
            return

        # if yandex_bot.moderator.moderate(user_message, user_id, session_id).decision == "flag":
        #     await update.message.reply_text(BOT_MESSAGES["malicious_blocked"])
        #     return

        if dialogue_bot.moderator.moderate(user_message, user_id, session_id).decision == "block":
            await update.message.reply_text(BOT_MESSAGES["moderator_blocked"])
            return

        # Используем ID чата как session_id для изоляции разговоров
        response = dialogue_bot.ask_gpt(user_message, session_id)

        log_user_action(
            user_id=user_id,
            session_id=session_id,
            action="response_sent",
            details=f"Response length: {len(response)} chars"
        )

        logger.info(f"Response sent to user @{username} ({user_id}) in session {session_id}: {response[:100]}...")
        await update.message.reply_text(response)

    except Exception as e:
        log_user_action(
            user_id=user_id,
            session_id=session_id,
            action="message_processing_failed",
            details=f"Error: {str(e)}",
            level="ERROR"
        )

        logger.error(f"Error handling message from user @{username} ({user_id}) in session {session_id}: {str(e)}")
        await update.message.reply_text(BOT_MESSAGES["error"])


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    user_id = str(update.effective_user.id) if update and update.effective_user else "unknown"
    session_id = str(update.effective_chat.id) if update and update.effective_chat else "unknown"
    username = update.effective_user.username if update and update.effective_user else "unknown"

    log_system_event(
        event="telegram_error",
        details=f"User: @{username} ({user_id}), Session: {session_id}, Error: {context.error}",
        level="ERROR"
    )

    logger.error(f"Update {update} caused error {context.error} for user @{username} ({user_id})")

    if update and update.effective_message:
        log_user_action(
            user_id=user_id,
            session_id=session_id,
            action="error_message_sent",
            details=f"Error: {str(context.error)}",
            level="ERROR"
        )

        await update.effective_message.reply_text(BOT_MESSAGES["telegram_error"])
