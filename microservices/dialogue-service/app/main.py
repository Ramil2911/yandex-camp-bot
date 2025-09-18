import time
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from .config import settings
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


@app.post("/dialogue", response_model=DialogueResponse)
async def process_dialogue(request: DialogueRequest):
    """Обработка диалогового запроса"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        result = await dialogue_bot.process_message(
            request.message,
            request.session_id,
            request.context
        )

        return DialogueResponse(**result)

    except Exception as e:
        logger.error(f"Dialogue processing failed for session {request.session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dialogue failed: {str(e)}")


@app.post("/clear-memory", response_model=ClearMemoryResponse)
async def clear_memory(request: ClearMemoryRequest):
    """Очистка памяти разговора"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        messages_cleared = dialogue_bot.clear_memory(request.session_id)

        return ClearMemoryResponse(
            success=True,
            message="Memory cleared successfully",
            messages_cleared=messages_cleared
        )

    except Exception as e:
        logger.error(f"Memory clear failed for session {request.session_id}: {str(e)}")
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

    session_info = dialogue_bot.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    return session_info.dict()


@app.post("/cleanup")
async def cleanup_sessions():
    """Очистка старых сессий"""
    if not dialogue_bot:
        raise HTTPException(status_code=503, detail="DialogueBot not available")

    try:
        dialogue_bot.cleanup_old_sessions()
        return {"message": "Sessions cleaned up successfully"}
    except Exception as e:
        logger.error(f"Session cleanup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    llm_status = "available" if dialogue_bot else "unavailable"

    stats = {}
    if dialogue_bot:
        stats = dialogue_bot.get_stats().dict()

    return DialogueHealthCheckResponse(
        status="healthy" if llm_status == "available" else "degraded",
        service="dialogue-service",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
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
            "model_name": settings.model_config["model_name"],
            "temperature": settings.model_config["temperature"],
            "max_memory_sessions": settings.dialogue_config["max_memory_sessions"],
            "session_timeout_hours": settings.dialogue_config["session_timeout_hours"]
        }
    }


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
            "cleanup": "POST /cleanup",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    }
