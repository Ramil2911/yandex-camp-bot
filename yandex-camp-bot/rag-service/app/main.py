import time
import logging
from fastapi import FastAPI, HTTPException
from loguru import logger

from common.config import config
from common.utils.tracing_middleware import TracingMiddleware, log_error
from common.utils import BaseService
from .models import (
    RAGSearchRequest, RAGSearchResponse, RAGSystemInfo,
    RAGHealthCheckResponse, LogEntry
)
from .rag_system import RAGSystem

# Глобальные переменные
rag_system = None


class RAGService(BaseService):
    """RAG Service с использованием базового класса"""

    def __init__(self):
        super().__init__(
            service_name="rag-service",
            version="1.0.0",
            description="Сервис поиска и извлечения информации из документов",
            dependencies={"rag_system": "available", "vectorstore": "available"}
        )

    async def on_startup(self):
        """Создание RAG системы (ленивая инициализация для serverless)"""
        global rag_system

        try:
            # Создаем объект RAG системы, но не инициализируем его сразу
            rag_system = RAGSystem()
            self.logger.info("RAG System created successfully with FULL SECURITY PIPELINE (will initialize on first request)")
        except Exception as e:
            self.logger.error(f"Failed to create RAG System: {e}")

            # Отправляем информацию об ошибке в monitoring-service
            self.handle_error_response(
                error=e,
                context={
                    "operation": "rag_system_creation",
                    "data_directory": config.data_directory,
                    "chroma_db_directory": config.chroma_db_directory
                }
            )

            rag_system = None
            raise e

    async def on_shutdown(self):
        """Очистка ресурсов"""
        global rag_system
        if rag_system:
            # Здесь можно добавить очистку ресурсов rag_system
            pass

    async def check_dependencies(self):
        """Проверка зависимостей RAG service"""
        dependencies_status = {}

        if rag_system:
            system_info = rag_system.get_system_info()
            dependencies_status["rag_system"] = "ready" if system_info.status == "ready" else system_info.status
            dependencies_status["vectorstore"] = "available" if system_info.document_count > 0 else "empty"
        else:
            dependencies_status["rag_system"] = "unavailable"
            dependencies_status["vectorstore"] = "unavailable"

        return dependencies_status

    def create_health_response(self, status: str, service_status: str = None, additional_stats: dict = None):
        """Создание health check ответа для RAG service с проверкой безопасности"""
        if rag_system:
            system_info = rag_system.get_system_info()

            # Определяем статусы
            if system_info.status == "ready":
                rag_status = "ready"
                vectorstore_status = "available" if system_info.document_count > 0 else "empty"
            else:
                rag_status = system_info.status
                vectorstore_status = system_info.status
                
            # БЕЗОПАСНОСТЬ: проверяем наличие QueryProcessor
            security_pipeline_status = "enabled" if rag_system.query_processor else "disabled"
        else:
            rag_status = "unavailable"
            vectorstore_status = "unavailable"
            security_pipeline_status = "unknown"

        # Добавляем информацию о безопасности в статистику
        security_stats = additional_stats or {}
        security_first = config.rag_config.get("security_first", True)
        security_stats.update({
            "security_pipeline": security_pipeline_status,
            "llm_analysis_enabled": security_first,
            "full_pipeline_mode": security_first,
            "security_first": security_first
        })

        return RAGHealthCheckResponse(
            status=status,
            service=self.service_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            rag_status=rag_status,
            vectorstore_status=vectorstore_status,
            stats=security_stats
        )


# Создаем экземпляр сервиса
service = RAGService()
app = service.app


@app.post("/search", response_model=RAGSearchResponse)
async def search_documents(request: RAGSearchRequest):
    """Поиск релевантных документов с улучшенным анализом"""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG System not available")

    try:
        result = await rag_system.search_relevant_docs(
            request.query, request.user_id, request.session_id
        )

        # Создаем ответ, включая новые поля анализа если они есть
        response_data = {
            "context": result["context"],
            "documents_found": result["documents_found"],
            "search_time": result["search_time"],
            "documents_info": result.get("documents_info", []),
            "similarity_scores": result.get("similarity_scores", []),
            "error": result.get("error")
        }

        # Добавляем новые поля если они есть (для обратной совместимости)
        if "analysis_result" in result and result["analysis_result"]:
            response_data["analysis_result"] = result["analysis_result"]
        if "queries_used" in result and result["queries_used"]:
            response_data["queries_used"] = result["queries_used"]

        return RAGSearchResponse(**response_data)

    except Exception as e:
        logger.error(f"Search failed for user {request.user_id}: {str(e)}")

        # Отправляем детальную информацию об ошибке в monitoring-service
        log_error(
            service="rag-service",
            error_type=type(e).__name__,
            error_message=f"RAG search failed: {str(e)}",
            user_id=request.user_id,
            session_id=request.session_id,
            context={
                "operation": "search_documents",
                "query_length": len(request.query) if request.query else 0,
                "rag_system_available": rag_system is not None
            }
        )

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
        
        # Отправляем информацию об ошибке в monitoring-service
        log_error(
            service="rag-service",
            error_type=type(e).__name__,
            error_message=f"Document reload failed: {str(e)}",
            context={
                "operation": "reload_documents",
                "rag_system_available": rag_system is not None,
                "data_directory": config.data_directory
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")




@app.get("/stats")
async def get_stats():
    """Получение статистики сервиса"""
    if not rag_system:
        return {"error": "RAG System not initialized"}

    system_info = rag_system.get_system_info()

    return {
        "service": "rag-service",
        "rag_config": config.rag_config,
        "system_info": system_info.dict(),
        "embedding_model": config.embedding_config["model_name"],
        "data_directory": config.data_directory,
        "chroma_db_directory": config.chroma_db_directory
    }


