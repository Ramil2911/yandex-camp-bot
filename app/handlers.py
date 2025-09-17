from telegram import Update
from telegram.ext import ContextTypes

from app.utils.config import BOT_MESSAGES
from app.llms import dialogue_bot
from app.utils.log import logger, log_user_action, log_security_event, log_error, log_system_event
from app.security.heuristics import is_malicious_prompt


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(user_id, chat_id, "start", f"@{username}")

    await update.message.reply_text(BOT_MESSAGES["start"])


async def clear_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка памяти разговора"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(user_id, session_id, "clear_memory", f"@{username}")
    dialogue_bot.clear_memory(session_id)
    await update.message.reply_text(BOT_MESSAGES["memory_cleared"])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(user_id, session_id, "help", f"@{username}")
    await update.message.reply_text(BOT_MESSAGES["help"])


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику бота"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(user_id, session_id, "stats", f"@{username}")

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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_message = update.message.text
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    # Не логируем обычные сообщения, только проблемные
    if not user_message.strip():
        log_user_action(user_id, session_id, "empty_message", f"@{username}")
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
            log_security_event(user_id, session_id, "malicious_blocked", f"@{username}")
            await update.message.reply_text(BOT_MESSAGES["malicious_blocked"])
            return

        # if yandex_bot.moderator.moderate(user_message, user_id, session_id).decision == "flag":
        #     await update.message.reply_text(BOT_MESSAGES["malicious_blocked"])
        #     return

        if dialogue_bot.moderator.moderate(user_message, user_id, session_id).decision == "block":
            log_security_event(user_id, session_id, "moderator_blocked", f"@{username}")
            await update.message.reply_text(BOT_MESSAGES["moderator_blocked"])
            return

        # Обычные сообщения не логируем
        response = dialogue_bot.ask_gpt(user_message, session_id)
        await update.message.reply_text(response)

    except Exception as e:
        log_error(user_id, session_id, f"Message processing failed: {str(e)}")
        await update.message.reply_text(BOT_MESSAGES["error"])


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    user_id = str(update.effective_user.id) if update and update.effective_user else "unknown"
    session_id = str(update.effective_chat.id) if update and update.effective_chat else "unknown"
    username = update.effective_user.username if update and update.effective_user else "unknown"

    log_error(user_id, session_id, f"Telegram error: {str(context.error)}")

    if update and update.effective_message:
        await update.effective_message.reply_text(BOT_MESSAGES["telegram_error"])
