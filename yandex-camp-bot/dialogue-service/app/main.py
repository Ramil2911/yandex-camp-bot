import time
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware, log_error, monitoring_client
from .models import (
    DialogueRequest, DialogueResponse, ClearMemoryRequest, ClearMemoryResponse,
    DialogueHealthCheckResponse, LogEntry
)
from .dialogue_bot import DialogueBot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
dialogue_bot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global dialogue_bot

    logger.info("Starting Dialogue Service...")

    # Инициализация диалогового бота
    try:
        dialogue_bot = DialogueBot()
        logger.info("DialogueBot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize DialogueBot: {e}")
        dialogue_bot = None

    yield

    logger.info("Shutting down Dialogue Service...")


app = FastAPI(
    title="Dialogue Service",
    description="Сервис диалогового ИИ с поддержкой контекста и памяти",
    version="1.0.0",
    lifespan=lifespan
)

# Добавляем middleware для трейсинга
app.middleware("http")(TracingMiddleware("dialogue-service"))


@app.post("/dialogue", response_model=DialogueResponse)
async def process_dialogue(request: DialogueRequest):
    """Обработка диалогового запроса"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        result = await dialogue_bot.process_message(
            request.message,
            request.session_id,
            request.user_id or "unknown",
            request.context
        )

        return DialogueResponse(**result)

    except Exception as e:
        logger.error(f"Dialogue processing failed for session {request.session_id}: {str(e)}")
        
        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="dialogue-service",
            error_type=type(e).__name__,
            error_message=f"Dialogue processing failed: {str(e)}",
            user_id=request.user_id or "unknown",
            session_id=request.session_id,
            context={
                "operation": "process_dialogue",
                "message_length": len(request.message) if request.message else 0,
                "has_context": bool(request.context),
                "dialogue_bot_available": dialogue_bot is not None
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Dialogue failed: {str(e)}")


@app.post("/clear-memory", response_model=ClearMemoryResponse)
async def clear_memory(request: ClearMemoryRequest):
    """Очистка памяти разговора"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        messages_cleared = await dialogue_bot.clear_memory(request.session_id)

        return ClearMemoryResponse(
            success=True,
            message="Memory cleared successfully",
            messages_cleared=messages_cleared
        )

    except Exception as e:
        logger.error(f"Memory clear failed for session {request.session_id}: {str(e)}")
        
        # Отправляем информацию об ошибке в monitoring-service
        log_error(
            service="dialogue-service",
            error_type=type(e).__name__,
            error_message=f"Memory clear failed: {str(e)}",
            user_id=request.user_id or "unknown",
            session_id=request.session_id,
            context={
                "operation": "clear_memory",
                "dialogue_bot_available": dialogue_bot is not None
            }
        )
        
        return ClearMemoryResponse(
            success=False,
            message=f"Failed to clear memory: {str(e)}",
            messages_cleared=0
        )


@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Получение информации о сессии"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    session_info = await dialogue_bot.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_info.dict()


@app.post("/cleanup")
async def cleanup_sessions():
    """Очистка старых сессий"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        await dialogue_bot.cleanup_old_sessions()
        return {"message": "Sessions cleaned up successfully"}
    except Exception as e:
        logger.error(f"Session cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    if not dialogue_bot:
        return DialogueHealthCheckResponse(
            status="unhealthy",
            service="dialogue-service",
            timestamp="2024-01-01T00:00:00Z",
            llm_status="unavailable",
            memory_sessions=0,
            stats={}
        )

    # Используем статус из dialogue_bot
    llm_status = dialogue_bot.llm_status
    stats = dialogue_bot.get_stats().dict()

    # Определяем общий статус
    if llm_status == "available":
        overall_status = "healthy"
    elif llm_status == "unavailable":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return DialogueHealthCheckResponse(
        status=overall_status,
        service="dialogue-service",
        timestamp="2024-01-01T00:00:00Z",
        llm_status=llm_status,
        memory_sessions=stats.get("active_sessions", 0),
        stats=stats
    )


@app.get("/stats")
async def get_stats():
    """Получение статистики сервиса"""
    if not dialogue_bot:
        return {"error": "DialogueBot not initialized"}

    return {
        "service": "dialogue-service",
        "dialogue_stats": dialogue_bot.get_stats().dict(),
        "config": {
            "model_name": config.model_config["model_name"],
            "temperature": config.model_config["temperature"],
            "max_memory_sessions": config.dialogue_config["max_memory_sessions"],
            "session_timeout_hours": config.dialogue_config["session_timeout_hours"]
        }
    }


@app.get("/dialogue/{session_id}/history")
async def get_dialogue_history(session_id: str, limit: int = 50):
    """Получение истории диалога"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        history = await dialogue_bot.get_dialogue_history(session_id, limit)
        return {
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Failed to get dialogue history for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@app.get("/dialogue/trace/{trace_id}")
async def search_dialogues_by_trace(trace_id: str):
    """Поиск диалогов по trace_id"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        dialogues = await dialogue_bot.search_dialogues_by_trace(trace_id)
        return {
            "trace_id": trace_id,
            "dialogues": dialogues,
            "count": len(dialogues)
        }
    except Exception as e:
        logger.error(f"Failed to search dialogues by trace {trace_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "Dialogue Service",
        "version": "1.0.0",
        "description": "Диалоговый ИИ с поддержкой контекста и памяти",
        "endpoints": {
            "dialogue": "POST /dialogue",
            "clear_memory": "POST /clear-memory",
            "session_info": "GET /session/{session_id}",
            "dialogue_history": "GET /dialogue/{session_id}/history",
            "search_by_trace": "GET /dialogue/trace/{trace_id}",
            "cleanup": "POST /cleanup",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    }
