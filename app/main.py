import os
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.utils.log import logger, log_user_action, log_security_event, log_api_call, log_metrics, log_system_event
from app.security.heuristics import is_malicious_prompt
from app.security.moderator import LLMModerator

load_dotenv()

# Переменные окружения для OpenAI API
OPENAI_API_KEY = os.getenv("YC_OPENAI_TOKEN")  # API-ключ для YandexGPT
FOLDER_ID = os.getenv("YC_FOLDER_ID")  # ID каталога Yandex Cloud
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")  # Токен Telegram-бота


class YandexGPTBot:
    def __init__(self):
        """Инициализация LangChain с YandexGPT"""
        log_system_event("bot_initialization_started", "Starting YandexGPT bot initialization")
        
        try:
            # Создаем LLM с настройками для YandexGPT
            self.llm = ChatOpenAI(
                model=f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
                openai_api_key=OPENAI_API_KEY,
                openai_api_base="https://llm.api.cloud.yandex.net/v1",
                temperature=0.6,
                max_tokens=2000
            )
            logger.debug(f"LLM initialized with model: gpt://{FOLDER_ID}/yandexgpt-lite/latest")
            
            self.moderator = LLMModerator(FOLDER_ID, OPENAI_API_KEY)
            logger.debug("Moderator initialized")
            
            # Создаем промпт с поддержкой истории
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", """Ты полезный AI-ассистент. Отвечай на русском языке. Старайся отвечать коротко и понятно.
                 Отвечай в стиле типичного двачера, завсегдатая /b. Детально копируй стиль и тон.
                 Примеры: «ОП, ты что, рофлишь? Кекнул с твоего поста.»
                 Ну всё, пошёл в армию мемов, удачи не ждите.
                 Когда тян сказала "нет", а ты уже вообразил свадьбу... жиза.»
                 Анон, хватит уже тред засорять, скринь и в мемы.
                 врывается в тред на капслоке ЭТО БЫЛО СУДЬБОЙ!!!»
                 """),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
            logger.debug("Prompt template created with system message and history support")
            
            # Создаем цепочку с поддержкой истории
            self.chain = self.prompt | self.llm
            logger.debug("LangChain chain created")
            
            # Создаем цепочку с историей сообщений
            self.conversation = RunnableWithMessageHistory(
                self.chain,
                self._get_session_history,
                input_messages_key="input",
                history_messages_key="history"
            )
            logger.debug("Conversation chain with message history created")
            
            # Словарь для хранения истории сессий
            self.store = {}
            
            # Статистика
            self.stats = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "malicious_requests": 0,
                "total_response_time": 0.0,
                "active_sessions": 0
            }
            
            log_system_event("bot_initialization_completed", "YandexGPT bot initialized successfully")
            
        except Exception as e:
            log_system_event("bot_initialization_failed", f"Failed to initialize bot: {str(e)}", "ERROR")
            raise

    def _get_session_history(self, session_id: str):
        """Получение истории сессии"""
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            self.stats["active_sessions"] = len(self.store)
            logger.debug(f"New session created: {session_id}, total sessions: {self.stats['active_sessions']}")
        return self.store[session_id]

    def ask_gpt(self, question, session_id="default"):
        """Запрос к YandexGPT через LangChain"""
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        log_user_action(
            user_id=session_id,
            session_id=session_id,
            action="gpt_request_started",
            details=f"Question length: {len(question)} chars"
        )
        
        try:
            # Используем современную цепочку с историей
            response = self.conversation.invoke(
                {"input": question},
                config={"configurable": {"session_id": session_id}}
            )
            
            duration = time.time() - start_time
            self.stats["successful_requests"] += 1
            self.stats["total_response_time"] += duration
            
            log_api_call(
                user_id=session_id,
                session_id=session_id,
                api_name="yandex_gpt",
                duration=duration,
                success=True,
                details=f"Response length: {len(response.content)} chars"
            )
            
            log_metrics(
                user_id=session_id,
                session_id=session_id,
                metric_name="response_time",
                value=duration,
                unit="seconds"
            )
            
            log_user_action(
                user_id=session_id,
                session_id=session_id,
                action="gpt_request_completed",
                details=f"Duration: {duration:.3f}s, Response length: {len(response.content)} chars"
            )
            
            return response.content

        except Exception as e:
            duration = time.time() - start_time
            self.stats["failed_requests"] += 1
            
            log_api_call(
                user_id=session_id,
                session_id=session_id,
                api_name="yandex_gpt",
                duration=duration,
                success=False,
                details=f"Error: {str(e)}"
            )
            
            log_user_action(
                user_id=session_id,
                session_id=session_id,
                action="gpt_request_failed",
                details=f"Error: {str(e)}, Duration: {duration:.3f}s",
                level="ERROR"
            )
            
            logger.error(f"Error in ask_gpt for session {session_id}: {str(e)}")
            raise

    def clear_memory(self, session_id="default"):
        """Очистка памяти разговора"""
        if session_id in self.store:
            message_count = len(self.store[session_id].messages)
            self.store[session_id].clear()
            
            log_user_action(
                user_id=session_id,
                session_id=session_id,
                action="memory_cleared",
                details=f"Cleared {message_count} messages from history"
            )
            
            logger.info(f"Memory cleared for session {session_id}, removed {message_count} messages")
        else:
            logger.warning(f"Attempted to clear memory for non-existent session: {session_id}")
    
    def get_stats(self):
        """Получение статистики бота"""
        avg_response_time = (
            self.stats["total_response_time"] / self.stats["successful_requests"] 
            if self.stats["successful_requests"] > 0 else 0
        )
        
        stats = {
            **self.stats,
            "average_response_time": avg_response_time,
            "success_rate": (
                self.stats["successful_requests"] / self.stats["total_requests"] 
                if self.stats["total_requests"] > 0 else 0
            )
        }
        
        log_metrics(
            user_id="system",
            session_id="system",
            metric_name="bot_stats",
            value=stats["total_requests"],
            unit="total_requests"
        )
        
        return stats


# Создаем экземпляр бота
yandex_bot = YandexGPTBot()


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
    
    await update.message.reply_text(
        "Привет! Я бот для работы с Yandex GPT."
        "Я помню наш разговор! Просто напиши мне свой вопрос.\n\n"
        "Доступные команды:\n"
        "/clear - очистить память разговора\n"
        "/help - показать справку\n"
        "/stats - показать статистику бота"
    )


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
    
    yandex_bot.clear_memory(session_id)
    await update.message.reply_text("Память разговора очищена!")
    
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
    
    help_text = """
🤖 **YandexGPT Bot**

**Команды:**
/start - начать работу
/clear - очистить память разговора
/help - показать эту справку
/stats - показать статистику бота

Просто напишите ваш вопрос, и я отвечу!
    """
    await update.message.reply_text(help_text)
    
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
    
    stats = yandex_bot.get_stats()
    
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
        await update.message.reply_text("Пожалуйста, введите вопрос")
        return

    try:
        # Показываем статус "печатает"
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Проверка на вредоносные промпты
        if is_malicious_prompt(user_message, user_id, session_id):
            yandex_bot.stats["malicious_requests"] += 1
            
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
            await update.message.reply_text("Извините, я не могу ответить на этот вопрос.")
            return
        
       #if yandex_bot.moderator.moderate(user_message, user_id, session_id).decision == "flag":
        #    await update.message.reply_text("Извините, я не могу ответить на этот вопрос.")
         #   return
        
        if yandex_bot.moderator.moderate(user_message, user_id, session_id).decision == "block":
            await update.message.reply_text("Извините, я не могу ответить на это.")
            return

        # Используем ID чата как session_id для изоляции разговоров
        response = yandex_bot.ask_gpt(user_message, session_id)
        
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
        await update.message.reply_text(
            "Извините, произошла ошибка при обработке вашего запроса. "
            "Пожалуйста, попробуйте позже."
        )


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
        
        await update.effective_message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте позже."
        )


def main():
    """Основная функция"""
    try:
        log_system_event("bot_startup_started", "Starting bot initialization")
        
        # Проверяем переменные окружения
        if not TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN not found in environment variables")
        if not OPENAI_API_KEY:
            raise ValueError("YC_OPENAI_TOKEN not found in environment variables")
        if not FOLDER_ID:
            raise ValueError("YC_FOLDER_ID not found in environment variables")
        
        log_system_event("environment_check_passed", "All required environment variables found")
        
        # Проверяем инициализацию LangChain
        logger.info("LangChain with YandexGPT initialized successfully")

        application = Application.builder().token(TELEGRAM_TOKEN).build()
        log_system_event("telegram_application_created", "Telegram application created successfully")

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear_memory))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        log_system_event("handlers_registered", "All command and message handlers registered")
        logger.info("Бот с LangChain запускается...")
        
        log_system_event("bot_startup_completed", "Bot startup completed successfully")
        application.run_polling()

    except Exception as e:
        log_system_event("bot_startup_failed", f"Failed to start bot: {str(e)}", "ERROR")
        logger.error(f"Failed to start bot: {str(e)}")
        raise


if __name__ == "__main__":
    main()