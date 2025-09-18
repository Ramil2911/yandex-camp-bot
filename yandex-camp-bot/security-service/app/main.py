import time
import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware, log_error, log_info, monitoring_client
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
        # Проверяем наличие необходимых переменных окружения
        if not config.yc_folder_id or not config.yc_folder_id.strip():
            logger.error("YC_FOLDER_ID environment variable is not set or empty")
            raise ValueError("YC_FOLDER_ID is required")

        if not config.yc_openai_token or not config.yc_openai_token.strip():
            logger.error("YC_OPENAI_TOKEN environment variable is not set or empty")
            raise ValueError("YC_OPENAI_TOKEN is required")

        moderator = LLMModerator(
            folder_id=config.yc_folder_id.strip(),
            openai_api_key=config.yc_openai_token.strip()
        )
        logger.info("LLM Moderator initialized successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("LLM Moderator will not be available. Service will work with heuristics only.")
        
        # Отправляем ошибку в мониторинг синхронно
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(monitoring_client.report_error(
                service="security-service",
                error_type="ConfigurationError",
                error_message=str(e),
                context={"component": "LLMModerator", "error": "Configuration validation failed"}
            ))
            loop.close()
        except Exception as monitoring_error:
            logger.error(f"Failed to send error to monitoring: {monitoring_error}")
        
        moderator = None
    except Exception as e:
        logger.error(f"Failed to initialize LLM Moderator: {e}")
        logger.error("LLM Moderator will not be available. Service will work with heuristics only.")
        
        # Отправляем ошибку в мониторинг синхронно
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(monitoring_client.report_error(
                service="security-service",
                error_type="InitializationError",
                error_message=str(e),
                context={"component": "LLMModerator", "error": "LLM initialization failed"}
            ))
            loop.close()
        except Exception as monitoring_error:
            logger.error(f"Failed to send error to monitoring: {monitoring_error}")
        
        moderator = None

    yield

    logger.info("Shutting down Security Service...")


app = FastAPI(
    title="Security Service",
    description="Сервис модерации и безопасности для проверки пользовательских запросов",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем middleware для трейсинга
app.middleware("http")(TracingMiddleware("security-service"))


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
        if is_malicious and config.security_config["block_suspicious"]:
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

        # Отправляем лог в мониторинг для важных событий
        log_level = "WARNING" if not response.allowed else "INFO"
        log_info(
            #level=log_level,
            service="security-service",
            message=f"Security check: {response.allowed}, confidence={response.confidence:.2f}",
            user_id=request.user_id,
            session_id=request.session_id,
            extra={
                "category": response.category,
                "reason": response.reason,
                "processing_time": processing_time
            }
        )

        # Отправляем детальную информацию о нарушениях безопасности в monitoring-service
        if not response.allowed:
            # Создаем детальную запись о нарушении безопасности
            security_violation = {
                "trace_id": f"security-{int(time.time())}-{uuid.uuid4().hex[:8]}",
                "request_id": f"req-{int(time.time())}",
                "service": "security-service",
                "error_type": "SecurityViolation",
                "error_message": f"Security violation detected: {response.reason}",
                "stack_trace": None,
                "context": {
                    "user_message": request.message,
                    "category": response.category,
                    "confidence": response.confidence,
                    "processing_time": processing_time,
                    "heuristic_check": is_malicious,
                    "llm_available": moderator is not None
                },
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": request.user_id,
                "session_id": request.session_id,
                "category": "security"
            }

            # Отправляем асинхронно с использованием данных из security_violation
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(monitoring_client.report_error(
                        service=security_violation["service"],
                        error_type=security_violation["error_type"],
                        error_message=security_violation["error_message"],
                        user_id=security_violation["user_id"],
                        session_id=security_violation["session_id"],
                        trace_id=security_violation["trace_id"],  # ДОБАВИТЬ trace_id
                        request_id=security_violation["request_id"],  # ДОБАВИТЬ request_id
                        context=security_violation["context"]
                    ))
                else:
                    loop.run_until_complete(monitoring_client.report_error(
                        service=security_violation["service"],
                        error_type=security_violation["error_type"],
                        error_message=security_violation["error_message"],
                        user_id=security_violation["user_id"],
                        session_id=security_violation["session_id"],
                        trace_id=security_violation["trace_id"],  # ДОБАВИТЬ trace_id
                        request_id=security_violation["request_id"],  # ДОБАВИТЬ request_id
                        context=security_violation["context"]
                    ))
            except Exception as monitoring_error:
                logger.error(f"Failed to send security violation to monitoring: {monitoring_error}")

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
            "block_suspicious": config.security_config["block_suspicious"],
            "max_request_length": config.security_config["max_request_length"]
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
