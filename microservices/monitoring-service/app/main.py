import time
import logging
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from .config import settings
from .models import (
    LogEntry, LogEntryCreate, LogEntryResponse,
    MetricsEntry, MetricsEntryCreate, MetricsEntryResponse,
    LogQuery, BulkLogResponse, MonitoringHealthCheckResponse, SystemStats
)
from .database import (
    get_db, LogEntryDB, MetricsEntryDB, ServiceHealthDB,
    init_db
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД при запуске
db_initialized = init_db()

app = FastAPI(
    title="Monitoring Service",
    description="Сервис логирования и мониторинга микросервисов",
    version="1.0.0"
)


@app.post("/logs", response_model=LogEntryResponse)
async def create_log_entry(
    log_entry: LogEntryCreate,
    db: Session = Depends(get_db)
):
    """Создание записи лога"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Создание записи в БД
        db_entry = LogEntryDB(
            level=log_entry.level,
            service=log_entry.service,
            message=log_entry.message,
            user_id=log_entry.user_id,
            session_id=log_entry.session_id,
            extra=log_entry.extra,
            timestamp=log_entry.timestamp
        )

        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        return LogEntryResponse(
            id=db_entry.id,
            level=db_entry.level,
            service=db_entry.service,
            message=db_entry.message,
            user_id=db_entry.user_id,
            session_id=db_entry.session_id,
            extra=db_entry.extra,
            timestamp=db_entry.timestamp,
            created_at=db_entry.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create log entry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create log: {str(e)}")


@app.post("/logs/bulk", response_model=BulkLogResponse)
async def create_bulk_logs(
    log_entries: List[LogEntryCreate],
    db: Session = Depends(get_db)
):
    """Массовое создание записей логов"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    start_time = time.time()
    inserted = 0
    errors = 0

    try:
        for log_entry in log_entries:
            try:
                db_entry = LogEntryDB(
                    level=log_entry.level,
                    service=log_entry.service,
                    message=log_entry.message,
                    user_id=log_entry.user_id,
                    session_id=log_entry.session_id,
                    extra=log_entry.extra,
                    timestamp=log_entry.timestamp
                )
                db.add(db_entry)
                inserted += 1
            except Exception as e:
                logger.error(f"Failed to create log entry: {str(e)}")
                errors += 1

        db.commit()

        return BulkLogResponse(
            inserted=inserted,
            errors=errors,
            processing_time=time.time() - start_time
        )

    except Exception as e:
        logger.error(f"Failed to create bulk logs: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk insert failed: {str(e)}")


@app.get("/logs", response_model=List[LogEntryResponse])
async def get_logs(
    query: LogQuery = None,
    db: Session = Depends(get_db)
):
    """Получение логов с фильтрацией"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Базовый запрос
        q = db.query(LogEntryDB)

        # Применение фильтров
        if query:
            if query.service:
                q = q.filter(LogEntryDB.service == query.service)
            if query.level:
                q = q.filter(LogEntryDB.level == query.level)
            if query.user_id:
                q = q.filter(LogEntryDB.user_id == query.user_id)
            if query.session_id:
                q = q.filter(LogEntryDB.session_id == query.session_id)
            if query.start_date:
                q = q.filter(LogEntryDB.timestamp >= query.start_date)
            if query.end_date:
                q = q.filter(LogEntryDB.timestamp <= query.end_date)

        # Пагинация
        q = q.order_by(LogEntryDB.timestamp.desc())
        if query:
            q = q.limit(query.limit).offset(query.offset)

        results = q.all()

        return [
            LogEntryResponse(
                id=entry.id,
                level=entry.level,
                service=entry.service,
                message=entry.message,
                user_id=entry.user_id,
                session_id=entry.session_id,
                extra=entry.extra,
                timestamp=entry.timestamp,
                created_at=entry.created_at
            )
            for entry in results
        ]

    except Exception as e:
        logger.error(f"Failed to get logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@app.post("/metrics", response_model=MetricsEntryResponse)
async def create_metrics_entry(
    metrics_entry: MetricsEntryCreate,
    db: Session = Depends(get_db)
):
    """Создание записи метрики"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_entry = MetricsEntryDB(
            service=metrics_entry.service,
            metric_name=metrics_entry.metric_name,
            value=metrics_entry.value,
            tags=metrics_entry.tags,
            timestamp=metrics_entry.timestamp
        )

        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        return MetricsEntryResponse(
            id=db_entry.id,
            service=db_entry.service,
            metric_name=db_entry.metric_name,
            value=db_entry.value,
            tags=db_entry.tags,
            timestamp=db_entry.timestamp,
            created_at=db_entry.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create metrics entry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create metrics: {str(e)}")


@app.get("/stats", response_model=SystemStats)
async def get_system_stats(db: Session = Depends(get_db)):
    """Получение общей статистики системы"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Общее количество логов
        total_logs = db.query(LogEntryDB).count()

        # Логи за сегодня
        today = datetime.utcnow().date()
        logs_today = db.query(LogEntryDB).filter(
            LogEntryDB.timestamp >= today
        ).count()

        # Активные сервисы (логи за последний час)
        last_hour = datetime.utcnow() - timedelta(hours=1)
        active_services = db.query(LogEntryDB.service).filter(
            LogEntryDB.timestamp >= last_hour
        ).distinct().count()

        # Процент ошибок за 24 часа
        yesterday = datetime.utcnow() - timedelta(days=1)
        total_24h = db.query(LogEntryDB).filter(
            LogEntryDB.timestamp >= yesterday
        ).count()

        errors_24h = db.query(LogEntryDB).filter(
            LogEntryDB.timestamp >= yesterday,
            LogEntryDB.level.in_(['ERROR', 'CRITICAL'])
        ).count()

        error_rate_24h = (errors_24h / total_24h * 100) if total_24h > 0 else 0

        # Среднее время ответа (заглушка, в реальном проекте хранить метрики)
        avg_response_time = 0.5

        return SystemStats(
            total_logs=total_logs,
            logs_today=logs_today,
            active_services=active_services,
            error_rate_24h=error_rate_24h,
            avg_response_time=avg_response_time
        )

    except Exception as e:
        logger.error(f"Failed to get system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    database_status = "available" if db_initialized else "unavailable"

    stats = {}
    try:
        # Получить базовую статистику
        from .database import SessionLocal
        db = SessionLocal()
        total_logs = db.query(LogEntryDB).count()
        stats = {"total_logs": total_logs}
        db.close()
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")

    return MonitoringHealthCheckResponse(
        status="healthy" if database_status == "available" else "unhealthy",
        service="monitoring-service",
        timestamp="2024-01-01T00:00:00Z",  # В реальном проекте использовать datetime
        database_status=database_status,
        stats=stats
    )


@app.delete("/logs/cleanup")
async def cleanup_old_logs(days: int = 30, db: Session = Depends(get_db)):
    """Очистка старых логов"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        deleted_count = db.query(LogEntryDB).filter(
            LogEntryDB.timestamp < cutoff_date
        ).delete()

        db.commit()

        return {
            "message": f"Cleaned up {deleted_count} old log entries",
            "deleted_count": deleted_count
        }

    except Exception as e:
        logger.error(f"Failed to cleanup logs: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/")
async def root():
    """Информационная страница"""
    return {
        "service": "Monitoring Service",
        "version": "1.0.0",
        "description": "Сервис логирования и мониторинга микросервисов",
        "endpoints": {
            "create_log": "POST /logs",
            "bulk_logs": "POST /logs/bulk",
            "get_logs": "GET /logs",
            "create_metrics": "POST /metrics",
            "system_stats": "GET /stats",
            "health": "GET /health",
            "cleanup": "DELETE /logs/cleanup"
        }
    }
