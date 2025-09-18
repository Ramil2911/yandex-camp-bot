from telegram import Update
from telegram.ext import ContextTypes

from app.utils.config import BOT_MESSAGES
from app.llms import dialogue_bot
from app.utils.log import logger, log_user_action, log_security_event, log_error, log_system_event
from app.chains import TelegramBotPipeline, TelegramAdapter
from app.rag import RAGAdapter

# Создаем глобальные экземпляры пайплайна и адаптера
_bot_pipeline = None
_telegram_adapter = None
_rag_adapter = None


async def initialize_rag_system():
    """Инициализация RAG системы при старте бота"""
    global _rag_adapter
    
    try:
        _rag_adapter = RAGAdapter()
        # RAGAdapter инициализируется в конструкторе, но нужно дождаться загрузки документов
        if _rag_adapter.enabled and _rag_adapter.rag_system:
            # Дополнительно убеждаемся, что документы загружены
            await _rag_adapter._initialize_rag()
        logger.info("RAG система инициализирована при старте бота")
        return _rag_adapter
    except Exception as e:
        logger.error(f"Ошибка инициализации RAG системы: {e}")
        _rag_adapter = None
        raise


def get_pipeline_adapter():
    """Получение или создание пайплайна и адаптера"""
    global _bot_pipeline, _telegram_adapter, _rag_adapter
    
    if _bot_pipeline is None:
        # Создаем RAG этап с предварительно инициализированным адаптером
        from app.chains.rag_pipeline import RAGPipelineStage
        rag_stage = RAGPipelineStage(_rag_adapter) if _rag_adapter else None
        
        _bot_pipeline = TelegramBotPipeline(dialogue_bot, rag_stage)
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
    rag_stats = pipeline_stats.get("rag_stats", {})

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
• RAG обработано: {pipeline_stats.get('rag_processed', 0)}

🧠 **RAG этап:**
• Статус: {'✅ Включен' if rag_stats.get('enabled', False) else '❌ Отключен'}
• Запросов к RAG: {rag_stats.get('rag_requests', 0)}
• Успешных поисков: {rag_stats.get('rag_successes', 0)}
• Ошибок RAG: {rag_stats.get('rag_errors', 0)}
• Контекст добавлен: {rag_stats.get('context_added', 0)}
• Документов загружено: {rag_stats.get('rag_adapter_stats', {}).get('documents_loaded', 0)}
• Успешность RAG: {rag_stats.get('success_rate', 0):.1%}

⏱️ **Производительность:**
• Среднее время ответа: {dialogue_stats.get('average_response_time', 0):.2f}с
• Успешность пайплайна: {pipeline_stats.get('success_rate', 0):.1%}
• Успешность диалога: {dialogue_stats.get('success_rate', 0):.1%}

👥 **Сессии:**
• Активных сессий: {dialogue_stats.get('active_sessions', 0)}
    """

    await update.message.reply_text(stats_text)


async def rag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление RAG системой"""
    user_id = str(update.effective_user.id)
    session_id = str(update.effective_chat.id)
    username = update.effective_user.username or "unknown"

    log_user_action(user_id, session_id, "rag_command", f"@{username}")

    # Получаем информацию о RAG системе
    global _rag_adapter
    pipeline, adapter = get_pipeline_adapter()
    pipeline_stats = pipeline.get_pipeline_stats()
    rag_stats = pipeline_stats.get("rag_stats", {})
    
    # Информация о RAG адаптере
    rag_info = ""
    if _rag_adapter:
        rag_system_info = _rag_adapter.get_system_info()
        rag_info = f"""
🧠 **RAG система (Retrieval-Augmented Generation)**

📊 **Статус системы:**
• Состояние: {'✅ Включен' if rag_system_info.get('enabled', False) else '❌ Отключен'}
• Документов загружено: {rag_system_info.get('stats', {}).get('documents_loaded', 0)}
• Порог схожести: {rag_system_info.get('similarity_threshold', 0.7):.2f}

📈 **Статистика RAG:**
• Запросов к RAG: {rag_system_info.get('stats', {}).get('rag_queries', 0)}
• Успешных поисков: {rag_system_info.get('stats', {}).get('rag_successes', 0)}
• Ошибок: {rag_system_info.get('stats', {}).get('rag_errors', 0)}
• Успешность: {rag_system_info.get('stats', {}).get('success_rate', 0):.1%}
• Средняя длина контекста: {rag_system_info.get('stats', {}).get('average_context_length', 0):.0f} символов

📊 **Статистика пайплайна:**
• RAG обработано: {pipeline_stats.get('rag_processed', 0)}

ℹ️ **Информация:**
RAG инициализируется при старте бота и работает как отдельный этап в пайплайне
    """
    else:
        rag_info = """
🧠 **RAG система (Retrieval-Augmented Generation)**

❌ **Статус:** RAG система не инициализирована
• Возможные причины: ошибка при запуске, отсутствие документов, проблемы с конфигурацией

ℹ️ **Информация:**
Попробуйте перезапустить бота или проверьте логи для диагностики
        """

    await update.message.reply_text(rag_info)


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
