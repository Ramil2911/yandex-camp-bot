import time
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from .config import settings
from .models import SecurityCheckRequest, SecurityCheckResponse, SecurityHealthCheckResponse, LogEntry
from .moderator import LLMModerator
from .heuristics import is_malicious_prompt

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
moderator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global moderator

    logger.info("Starting Security Service...")

    # Инициализация модератора
    try:
        moderator = LLMModerator(
            folder_id=settings.yc_folder_id,
            openai_api_key=settings.yc_openai_token
        )
        logger.info("LLM Moderator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Moderator: {e}")
        moderator = None

    yield

    logger.info("Shutting down Security Service...")


app = FastAPI(
    title="Security Service",
    description="Сервис модерации и безопасности для проверки пользовательских запросов",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/moderate", response_model=SecurityCheckResponse)
async def moderate_message(request: SecurityCheckRequest):
    """Модерация сообщения"""
    start_time = time.time()

    try:
        # 1. Эвристическая проверка
        is_malicious, heuristic_reason, heuristic_confidence = is_malicious_prompt(
            request.message, request.user_id, request.session_id
        )

        # Если эвристика блокирует, возвращаем результат
        if is_malicious and settings.security_config["block_suspicious"]:
            processing_time = time.time() - start_time
            return SecurityCheckResponse(
                allowed=False,
                reason=f"Heuristic check: {heuristic_reason}",
                category="malware",
                confidence=heuristic_confidence,
                processing_time=processing_time
            )

        # 2. LLM-модерация (если доступна)
        if moderator:
            llm_verdict = moderator.moderate(request.message, request.user_id, request.session_id)

            allowed = llm_verdict.decision == "allow"
            reason = llm_verdict.reason or ""
            category = llm_verdict.categories

            # Комбинируем confidence
            llm_confidence = 0.8 if llm_verdict.decision == "block" else 0.6
            combined_confidence = max(heuristic_confidence, llm_confidence)

        else:
            # Fallback без LLM
            logger.warning("LLM Moderator not available, using heuristic only")
            allowed = not is_malicious
            reason = heuristic_reason or "Heuristic check passed"
            category = "malware" if is_malicious else None
            combined_confidence = heuristic_confidence

        processing_time = time.time() - start_time

        response = SecurityCheckResponse(
            allowed=allowed,
            reason=reason,
            category=category,
            confidence=combined_confidence,
            processing_time=processing_time
        )

        # Логируем результат
        logger.info(
            f"Security check for user {request.user_id}: "
            f"allowed={response.allowed}, "
            f"confidence={response.confidence:.2f}, "
            f"time={processing_time:.2f}s"
        )

        return response

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Security check failed for user {request.user_id}: {str(e)}")

        # Fallback: разрешаем при ошибке
        return SecurityCheckResponse(
            allowed=True,
            reason=f"Security check error: {str(e)}",
            category=None,
            confidence=0.0,
            processing_time=processing_time
        )


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    llm_status = "available" if moderator else "unavailable"

    stats = {}
    if moderator:
        stats = moderator.get_stats()

    return SecurityHealthCheckResponse(
        status="healthy" if llm_status == "available" else "degraded",
        service="security-service",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
        llm_status=llm_status,
        stats=stats
    )


@app.get("/stats")
async def get_stats():
    """Получение статистики сервиса"""
    if not moderator:
        return {"error": "Moderator not initialized"}

    return {
        "service": "security-service",
        "moderator_stats": moderator.get_stats(),
        "config": {
            "block_suspicious": settings.security_config["block_suspicious"],
            "max_request_length": settings.security_config["max_request_length"]
        }
    }


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "Security Service",
        "version": "1.0.0",
        "description": "Модерация и безопасность для пользовательских запросов",
        "endpoints": {
            "moderate": "POST /moderate",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    }
