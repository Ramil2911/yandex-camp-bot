import time
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from .config import settings
from .models import (
    RAGSearchRequest, RAGSearchResponse, RAGSystemInfo,
    RAGHealthCheckResponse, LogEntry
)
from .rag_system import RAGSystem

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
rag_system = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global rag_system

    logger.info("Starting RAG Service...")

    # Инициализация RAG системы
    try:
        rag_system = RAGSystem()
        logger.info("RAG System initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG System: {e}")
        rag_system = None

    yield

    logger.info("Shutting down RAG Service...")


app = FastAPI(
    title="RAG Service",
    description="Сервис поиска и извлечения информации из документов",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/search", response_model=RAGSearchResponse)
async def search_documents(request: RAGSearchRequest):
    """Поиск релевантных документов"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG System not available")

    try:
        result = await rag_system.search_relevant_docs(
            request.query, request.user_id, request.session_id
        )

        return RAGSearchResponse(**result)

    except Exception as e:
        logger.error(f"Search failed for user {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/info", response_model=RAGSystemInfo)
async def get_system_info():
    """Получение информации о RAG системе"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG System not available")

    return rag_system.get_system_info()


@app.post("/reload")
async def reload_documents():
    """Перезагрузка документов"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG System not available")

    try:
        rag_system.reload_documents()
        return {"message": "Documents reloaded successfully"}
    except Exception as e:
        logger.error(f"Document reload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    rag_status = "available" if rag_system else "unavailable"

    vectorstore_status = "unknown"
    stats = {}

    if rag_system:
        try:
            system_info = rag_system.get_system_info()
            vectorstore_status = "available" if system_info.document_count > 0 else "empty"
            stats = system_info.stats
        except Exception as e:
            vectorstore_status = "error"
            logger.error(f"Health check failed: {str(e)}")

    return RAGHealthCheckResponse(
        status="healthy" if rag_status == "available" else "degraded",
        service="rag-service",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
        rag_status=rag_status,
        vectorstore_status=vectorstore_status,
        stats=stats
    )


@app.get("/stats")
async def get_stats():
    """Получение статистики сервиса"""
    if not rag_system:
        return {"error": "RAG System not initialized"}

    system_info = rag_system.get_system_info()

    return {
        "service": "rag-service",
        "rag_config": settings.rag_config,
        "system_info": system_info.dict(),
        "embedding_model": settings.embedding_config["model_name"],
        "data_directory": settings.data_directory,
        "chroma_db_directory": settings.chroma_db_directory
    }


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "RAG Service",
        "version": "1.0.0",
        "description": "Поиск и извлечение информации из документов",
        "endpoints": {
            "search": "POST /search",
            "info": "GET /info",
            "reload": "POST /reload",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    }
