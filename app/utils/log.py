from loguru import logger
import sys
import os
from datetime import datetime
from pathlib import Path

# Создаем директорию для логов
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Информативный формат для консоли
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}:{line:<6}</cyan> | "
    "<level>{message}</level>"
)

# Подробный формат для файлов с информацией об источнике
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level:<8} | "
    "{name}:{line:<6} | "
    "{extra[user_id]:<10} | "
    "{extra[session_id]:<10} | "
    "{message}"
)

# Простой формат для обычных логов
SIMPLE_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level:<8} | "
    "{name}:{line:<6} | "
    "{message}"
)

# Удаляем все существующие обработчики
logger.remove()

# Консольный вывод (INFO, WARNING, ERROR, CRITICAL)
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

# Функции логирования с детальной информацией
def log_user_action(user_id: str, session_id: str, action: str, details: str = "", level: str = "INFO"):
    """Логирование действий пользователя с деталями"""
    logger.bind(user_id=user_id, session_id=session_id, category="user_action").log(level, f"User action: {action} | {details}")

def log_security_event(user_id: str, session_id: str, event: str, details: str = "", severity: str = "WARNING"):
    """Логирование событий безопасности с деталями"""
    logger.bind(user_id=user_id, session_id=session_id, category="security").log(severity, f"Security event: {event} | {details}")

def log_error(user_id: str, session_id: str, error_msg: str):
    """Логирование ошибок с контекстом"""
    logger.bind(user_id=user_id, session_id=session_id, category="error").error(f"Error: {error_msg}")

def log_system_event(event: str, details: str = "", level: str = "INFO"):
    """Логирование системных событий с деталями"""
    logger.bind(user_id="system", session_id="system", category="system").log(level, f"System event: {event} | {details}")

def log_model_info(model_name: str, model_config: dict, component: str = "unknown"):
    """Логирование информации о моделях"""
    logger.bind(user_id="system", session_id="system", category="model").info(
        f"Model loaded: {model_name} | Component: {component} | Config: {model_config}"
    )

def log_bot_startup(component: str, details: str = ""):
    """Логирование запуска компонентов бота"""
    logger.bind(user_id="system", session_id="system", category="startup").info(f"Bot startup: {component} | {details}")

def log_config_info(config_name: str, config_value: str, source: str = "env"):
    """Логирование конфигурационной информации"""
    logger.bind(user_id="system", session_id="system", category="config").info(f"Config loaded: {config_name}={config_value} | Source: {source}")

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
