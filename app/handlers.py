from telegram import Update
from telegram.ext import ContextTypes

from app.utils.config import BOT_MESSAGES
from app.llms import dialogue_bot
from app.utils.log import logger, log_user_action, log_security_event, log_error, log_system_event
from app.chains import TelegramBotPipeline, TelegramAdapter

# Создаем глобальные экземпляры пайплайна и адаптера
_bot_pipeline = None
_telegram_adapter = None


def get_pipeline_adapter():
    """Получение или создание пайплайна и адаптера"""
    global _bot_pipeline, _telegram_adapter
    
    if _bot_pipeline is None:
        _bot_pipeline = TelegramBotPipeline(dialogue_bot)
        _telegram_adapter = TelegramAdapter(_bot_pipeline)
        logger.info("LangChain пайплайн и адаптер инициализированы")
    
    return _bot_pipeline, _telegram_adapter


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

    # Получаем статистику от LangChain пайплайна
    pipeline, adapter = get_pipeline_adapter()
    pipeline_stats = pipeline.get_pipeline_stats()
    dialogue_stats = pipeline_stats.get("dialogue_bot_stats", {})

    stats_text = f"""
📊 **Статистика бота (LangChain Pipeline)**

📈 **Общая статистика:**
• Всего запросов: {dialogue_stats.get('total_requests', 0)}
• Успешных: {dialogue_stats.get('successful_requests', 0)}
• Неудачных: {dialogue_stats.get('failed_requests', 0)}
• Подозрительных: {dialogue_stats.get('malicious_requests', 0)}

⚡ **Пайплайн:**
• Запросов пайплайна: {pipeline_stats.get('pipeline_requests', 0)}
• Успешных: {pipeline_stats.get('pipeline_successes', 0)}
• Ошибок: {pipeline_stats.get('pipeline_errors', 0)}
• Блокировок безопасности: {pipeline_stats.get('security_blocks', 0)}
• Блокировок модератора: {pipeline_stats.get('moderator_blocks', 0)}

⏱️ **Производительность:**
• Среднее время ответа: {dialogue_stats.get('average_response_time', 0):.2f}с
• Успешность пайплайна: {pipeline_stats.get('success_rate', 0):.1%}
• Успешность диалога: {dialogue_stats.get('success_rate', 0):.1%}

👥 **Сессии:**
• Активных сессий: {dialogue_stats.get('active_sessions', 0)}
    """

    await update.message.reply_text(stats_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений через LangChain пайплайн"""
    try:
        # Получаем пайплайн и адаптер
        pipeline, adapter = get_pipeline_adapter()
        
        # Обрабатываем сообщение через LangChain пайплайн
        response = await adapter.process_telegram_message(update, context)
        
        # Отправляем ответ
        await update.message.reply_text(response)

    except Exception as e:
        # Фолбэк логирование
        user_id = str(update.effective_user.id) if update.effective_user else "unknown"
        session_id = str(update.effective_chat.id) if update.effective_chat else "unknown"
        log_error(user_id, session_id, f"LangChain pipeline failed: {str(e)}")
        await update.message.reply_text(BOT_MESSAGES["error"])


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    user_id = str(update.effective_user.id) if update and update.effective_user else "unknown"
    session_id = str(update.effective_chat.id) if update and update.effective_chat else "unknown"
    username = update.effective_user.username if update and update.effective_user else "unknown"

    log_error(user_id, session_id, f"Telegram error: {str(context.error)}")

    if update and update.effective_message:
        await update.effective_message.reply_text(BOT_MESSAGES["telegram_error"])
