from loguru import logger
import sys
import os
from datetime import datetime
from pathlib import Path

# Создаем директорию для логов
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Форматирование для консоли: [Время] [Уровень] [Модуль:Строка] Сообщение
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level:<16}</level> | "
    "<cyan>{name}:{line:<4}</cyan> | "
    "<level>{message}</level>"
)

# Форматирование для файлов (без цветов)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level:<8} | "
    "{name}:{line:<4} | "
    "{extra[user_id]:<12} | "
    "{extra[session_id]:<12} | "
    "{extra[request_id]:<12} | "
    "{message}"
)

# Простой формат для обычных логов
SIMPLE_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level:<8} | "
    "{name}:{line:<4} | "
    "{message}"
)

# Удаляем все существующие обработчики
logger.remove()

# Консольный вывод (только INFO и выше)
logger.add(
    sys.stderr,
    format=CONSOLE_FORMAT,
    colorize=True,
    level="INFO",
    backtrace=True,
    diagnose=True,
    enqueue=True,
    filter=lambda record: record["level"].name in ["INFO", "WARNING", "ERROR", "CRITICAL"]
)

# Отдельный консольный вывод для DEBUG (только при необходимости)
if os.getenv("DEBUG_LOGGING", "false").lower() == "true":
    logger.add(
        sys.stderr,
        format=CONSOLE_FORMAT,
        colorize=True,
        level="DEBUG",
        enqueue=True,
        filter=lambda record: record["level"].name == "DEBUG"
    )

# Основной лог файл (все уровни)
logger.add(
    log_dir / "bot.log",
    format=SIMPLE_FILE_FORMAT,
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8"
)

# Лог ошибок (только ERROR и CRITICAL)
logger.add(
    log_dir / "errors.log",
    format=SIMPLE_FILE_FORMAT,
    level="ERROR",
    rotation="5 MB",
    retention="90 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8"
)

# Лог безопасности (подозрительные запросы)
logger.add(
    log_dir / "security.log",
    format=SIMPLE_FILE_FORMAT,
    level="WARNING",
    rotation="5 MB",
    retention="180 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8",
    filter=lambda record: "security" in record["extra"].get("category", "")
)

# Лог метрик (статистика)
logger.add(
    log_dir / "metrics.log",
    format=SIMPLE_FILE_FORMAT,
    level="INFO",
    rotation="1 day",
    retention="7 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8",
    filter=lambda record: "metrics" in record["extra"].get("category", "")
)

# Функции для структурированного логирования
def log_user_action(user_id: str, session_id: str, action: str, details: str = "", level: str = "INFO"):
    """Логирование действий пользователя"""
    logger.bind(
        user_id=user_id,
        session_id=session_id,
        request_id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}{hash(details) % 10000:04d}",
        category="user_action"
    ).log(level, f"User action: {action} | {details}")

def log_security_event(user_id: str, session_id: str, event: str, details: str = "", severity: str = "WARNING"):
    """Логирование событий безопасности"""
    logger.bind(
        user_id=user_id,
        session_id=session_id,
        request_id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}{hash(details) % 10000:04d}",
        category="security"
    ).log(severity, f"Security event: {event} | {details}")

def log_api_call(user_id: str, session_id: str, api_name: str, duration: float, success: bool, details: str = ""):
    """Логирование вызовов API"""
    level = "INFO" if success else "ERROR"
    logger.bind(
        user_id=user_id,
        session_id=session_id,
        request_id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}{hash(api_name) % 10000:04d}",
        category="api_call"
    ).log(level, f"API call: {api_name} | Duration: {duration:.3f}s | Success: {success} | {details}")

def log_metrics(user_id: str, session_id: str, metric_name: str, value: float, unit: str = ""):
    """Логирование метрик"""
    logger.bind(
        user_id=user_id,
        session_id=session_id,
        request_id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}{hash(metric_name) % 10000:04d}",
        category="metrics"
    ).info(f"Metric: {metric_name} = {value} {unit}")

def log_system_event(event: str, details: str = "", level: str = "INFO"):
    """Логирование системных событий"""
    logger.bind(
        user_id="system",
        session_id="system",
        request_id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}{hash(event) % 10000:04d}",
        category="system"
    ).log(level, f"System event: {event} | {details}")

# Пример использования:
# logger.debug("Debug message")
# logger.info("Info message")
# logger.warning("Warning message")
# logger.error("Error message")
# logger.critical("Critical message")
# log_user_action("12345", "session_1", "send_message", "Hello bot")
# log_security_event("12345", "session_1", "malicious_prompt_detected", "Prompt injection attempt")
# log_api_call("12345", "session_1", "yandex_gpt", 1.234, True, "Generated response")
# log_metrics("12345", "session_1", "response_time", 1.234, "seconds")
# log_system_event("bot_started", "YandexGPT bot initialized successfully")
