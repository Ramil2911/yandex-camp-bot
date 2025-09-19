import time
import logging
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta

from common.config import config
from common.utils import BaseService
from .models import (
    LogEntry, LogEntryCreate, LogEntryResponse,
    MetricsEntry, MetricsEntryCreate, MetricsEntryResponse,
    TraceEntry, TraceEntryCreate, TraceEntryResponse,
    ErrorEntry, ErrorEntryCreate, ErrorEntryResponse,
    LogQuery, BulkLogResponse, MonitoringHealthCheckResponse, SystemStats,
    TraceQuery, ErrorQuery, FullTraceResponse
)
from .database import (
    get_db, LogEntryDB, MetricsEntryDB, ServiceHealthDB,
    TraceEntryDB, ErrorEntryDB,
    init_db
)

# Глобальная переменная для статуса БД
db_initialized = False

class MonitoringService(BaseService):
    """Monitoring Service с использованием базового класса"""

    def __init__(self):
        super().__init__(
            service_name="monitoring-service",
            version="1.0.0",
            description="Сервис логирования и мониторинга микросервисов",
            dependencies={"database": "available"}
        )

    async def on_startup(self):
        """Инициализация БД"""
        global db_initialized
        db_initialized = init_db()
        if not db_initialized:
            raise Exception("Failed to initialize database")

    async def check_dependencies(self):
        """Проверка зависимостей monitoring service"""
        dependencies_status = {}
        dependencies_status["database"] = "available" if db_initialized else "unavailable"
        return dependencies_status

    def create_health_response(self, status: str, service_status: str = None, additional_stats: dict = None):
        """Создание health check ответа для monitoring service"""
        database_status = "available" if db_initialized else "unavailable"
        stats = additional_stats or {}

        # Получить базовую статистику
        try:
            from .database import SessionLocal
            db = SessionLocal()
            total_logs = db.query(LogEntryDB).count()
            stats["total_logs"] = total_logs
            db.close()
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")

        return MonitoringHealthCheckResponse(
            status="healthy" if database_status == "available" else "unhealthy",
            service=self.service_name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            database_status=database_status,
            stats=stats
        )


# Создаем экземпляр сервиса
service = MonitoringService()
app = service.app

# Простой тестовый endpoint
@app.get("/test")
async def test_endpoint():
    return {"status": "OK", "message": "Monitoring service is working"}


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
        today = datetime.now().date()
        logs_today = db.query(LogEntryDB).filter(
            LogEntryDB.timestamp >= today
        ).count()

        # Активные сервисы (логи за последний час)
        last_hour = datetime.now() - timedelta(hours=1)
        active_services = db.query(LogEntryDB.service).filter(
            LogEntryDB.timestamp >= last_hour
        ).distinct().count()

        # Процент ошибок за 24 часа
        yesterday = datetime.now() - timedelta(days=1)
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




@app.post("/traces", response_model=TraceEntryResponse)
async def create_trace_entry(
    trace_entry: TraceEntryCreate,
    db: Session = Depends(get_db)
):
    """Создание записи трейса"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_entry = TraceEntryDB(
            trace_id=trace_entry.trace_id,
            request_id=trace_entry.request_id,
            span_id=trace_entry.span_id,
            service=trace_entry.service,
            operation=trace_entry.operation,
            start_time=trace_entry.start_time,
            end_time=trace_entry.end_time,
            duration=trace_entry.duration,
            status=trace_entry.status,
            error_message=trace_entry.error_message,
            trace_metadata=trace_entry.metadata,
            user_id=trace_entry.user_id,
            session_id=trace_entry.session_id
        )

        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        return TraceEntryResponse(
            id=db_entry.id,
            trace_id=db_entry.trace_id,
            request_id=db_entry.request_id,
            span_id=db_entry.span_id,
            service=db_entry.service,
            operation=db_entry.operation,
            start_time=db_entry.start_time,
            end_time=db_entry.end_time,
            duration=db_entry.duration,
            status=db_entry.status,
            error_message=db_entry.error_message,
            metadata=db_entry.trace_metadata,
            user_id=db_entry.user_id,
            session_id=db_entry.session_id,
            created_at=db_entry.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create trace entry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create trace: {str(e)}")


@app.post("/errors", response_model=ErrorEntryResponse)
async def create_error_entry(
    error_entry: ErrorEntryCreate,
    db: Session = Depends(get_db)
):
    """Создание записи ошибки"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        db_entry = ErrorEntryDB(
            trace_id=error_entry.trace_id,
            request_id=error_entry.request_id,
            service=error_entry.service,
            error_type=error_entry.error_type,
            error_message=error_entry.error_message,
            stack_trace=error_entry.stack_trace,
            context=error_entry.context,
            timestamp=error_entry.timestamp,
            user_id=error_entry.user_id,
            session_id=error_entry.session_id,
            category=error_entry.category
        )

        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)

        return ErrorEntryResponse(
            id=db_entry.id,
            trace_id=db_entry.trace_id,
            request_id=db_entry.request_id,
            service=db_entry.service,
            error_type=db_entry.error_type,
            error_message=db_entry.error_message,
            stack_trace=db_entry.stack_trace,
            context=db_entry.context,
            timestamp=db_entry.timestamp,
            user_id=db_entry.user_id,
            session_id=db_entry.session_id,
            category=db_entry.category,
            created_at=db_entry.created_at
        )

    except Exception as e:
        logger.error(f"Failed to create error entry: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create error: {str(e)}")


@app.get("/traces", response_model=List[TraceEntryResponse])
async def get_traces(
    query: TraceQuery = None,
    db: Session = Depends(get_db)
):
    """Получение трейсов с фильтрацией"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        q = db.query(TraceEntryDB)

        if query:
            if query.trace_id:
                q = q.filter(TraceEntryDB.trace_id == query.trace_id)
            if query.request_id:
                q = q.filter(TraceEntryDB.request_id == query.request_id)
            if query.service:
                q = q.filter(TraceEntryDB.service == query.service)
            if query.operation:
                q = q.filter(TraceEntryDB.operation.ilike(f"%{query.operation}%"))
            if query.status:
                q = q.filter(TraceEntryDB.status == query.status)
            if query.user_id:
                q = q.filter(TraceEntryDB.user_id == query.user_id)
            if query.session_id:
                q = q.filter(TraceEntryDB.session_id == query.session_id)
            if query.start_date:
                q = q.filter(TraceEntryDB.start_time >= query.start_date)
            if query.end_date:
                q = q.filter(TraceEntryDB.start_time <= query.end_date)

        q = q.order_by(TraceEntryDB.start_time.desc())
        if query:
            q = q.limit(query.limit).offset(query.offset)

        results = q.all()

        return [
            TraceEntryResponse(
                id=entry.id,
                trace_id=entry.trace_id,
                request_id=entry.request_id,
                span_id=entry.span_id,
                service=entry.service,
                operation=entry.operation,
                start_time=entry.start_time,
                end_time=entry.end_time,
                duration=entry.duration,
                status=entry.status,
                error_message=entry.error_message,
                metadata=entry.trace_metadata,
                user_id=entry.user_id,
                session_id=entry.session_id,
                created_at=entry.created_at
            )
            for entry in results
        ]

    except Exception as e:
        logger.error(f"Failed to get traces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get traces: {str(e)}")


@app.get("/errors", response_model=List[ErrorEntryResponse])
async def get_errors(
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    service: Optional[str] = None,
    error_type: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Получение ошибок с фильтрацией"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        logger.info(f"Filtering errors with category={category}, service={service}, error_type={error_type}")
        q = db.query(ErrorEntryDB)

        # Применяем фильтры
        if trace_id:
            q = q.filter(ErrorEntryDB.trace_id == trace_id)
            logger.info(f"Applied trace_id filter: {trace_id}")
        if request_id:
            q = q.filter(ErrorEntryDB.request_id == request_id)
            logger.info(f"Applied request_id filter: {request_id}")
        if service:
            q = q.filter(ErrorEntryDB.service == service)
            logger.info(f"Applied service filter: {service}")
        if error_type:
            q = q.filter(ErrorEntryDB.error_type == error_type)
            logger.info(f"Applied error_type filter: {error_type}")
        if category:
            q = q.filter(ErrorEntryDB.category == category)
            logger.info(f"Applied category filter: {category}")
        if user_id:
            q = q.filter(ErrorEntryDB.user_id == user_id)
            logger.info(f"Applied user_id filter: {user_id}")
        if session_id:
            q = q.filter(ErrorEntryDB.session_id == session_id)
            logger.info(f"Applied session_id filter: {session_id}")
        if start_date:
            q = q.filter(ErrorEntryDB.timestamp >= start_date)
            logger.info(f"Applied start_date filter: {start_date}")
        if end_date:
            q = q.filter(ErrorEntryDB.timestamp <= end_date)
            logger.info(f"Applied end_date filter: {end_date}")

        q = q.order_by(ErrorEntryDB.timestamp.desc())
        q = q.limit(limit).offset(offset)

        results = q.all()

        return [
            ErrorEntryResponse(
                id=entry.id,
                trace_id=entry.trace_id,
                request_id=entry.request_id,
                service=entry.service,
                error_type=entry.error_type,
                error_message=entry.error_message,
                stack_trace=entry.stack_trace,
                context=entry.context,
                timestamp=entry.timestamp,
                user_id=entry.user_id,
                session_id=entry.session_id,
                category=entry.category,
                created_at=entry.created_at
            )
            for entry in results
        ]

    except Exception as e:
        logger.error(f"Failed to get errors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get errors: {str(e)}")


@app.get("/trace/{trace_id}", response_model=List[TraceEntryResponse])
async def get_trace_by_id(
    trace_id: str,
    db: Session = Depends(get_db)
):
    """Получение всех спанов для конкретного трейса"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        results = db.query(TraceEntryDB).filter(
            TraceEntryDB.trace_id == trace_id
        ).order_by(TraceEntryDB.start_time).all()

        return [
            TraceEntryResponse(
                id=entry.id,
                trace_id=entry.trace_id,
                request_id=entry.request_id,
                span_id=entry.span_id,
                service=entry.service,
                operation=entry.operation,
                start_time=entry.start_time,
                end_time=entry.end_time,
                duration=entry.duration,
                status=entry.status,
                error_message=entry.error_message,
                metadata=entry.trace_metadata,
                user_id=entry.user_id,
                session_id=entry.session_id,
                created_at=entry.created_at
            )
            for entry in results
        ]

    except Exception as e:
        logger.error(f"Failed to get trace {trace_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get trace: {str(e)}")


@app.get("/trace/{trace_id}/full", response_model=FullTraceResponse)
async def get_full_trace(
    trace_id: str,
    db: Session = Depends(get_db)
):
    """Получение полного трейса через все сервисы с деталями ошибок"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Получаем все спаны трейса
        trace_spans = db.query(TraceEntryDB).filter(
            TraceEntryDB.trace_id == trace_id
        ).order_by(TraceEntryDB.start_time).all()

        if not trace_spans:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Получаем все ошибки для этого трейса
        trace_errors = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.trace_id == trace_id
        ).order_by(ErrorEntryDB.timestamp).all()

        # Определяем основной request_id и другие метаданные
        first_span = trace_spans[0]
        request_id = first_span.request_id
        user_id = first_span.user_id
        session_id = first_span.session_id

        # Вычисляем общее время выполнения
        start_time = min(span.start_time for span in trace_spans)
        end_times = [span.end_time for span in trace_spans if span.end_time]
        end_time = max(end_times) if end_times else None
        total_duration = (end_time - start_time).total_seconds() * 1000 if end_time else None

        # Определяем общий статус
        has_errors = any(span.status == "error" for span in trace_spans)
        status = "error" if has_errors else "success"

        # Формируем путь через сервисы
        services_path = []
        for span in trace_spans:
            service_info = {
                "service": span.service,
                "operation": span.operation,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration": span.duration,
                "status": span.status,
                "error_message": span.error_message,
                "metadata": span.trace_metadata
            }
            services_path.append(service_info)

        # Формируем информацию об ошибках
        errors = []
        for error in trace_errors:
            error_info = {
                "service": error.service,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "category": error.category,
                "timestamp": error.timestamp.isoformat(),
                "stack_trace": error.stack_trace,
                "context": error.context
            }
            errors.append(error_info)

        return FullTraceResponse(
            request_id=request_id,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            total_duration=total_duration,
            status=status,
            services_path=services_path,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get full trace {trace_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get full trace: {str(e)}")


@app.get("/request/{request_id}/full", response_model=FullTraceResponse)
async def get_full_request_trace(
    request_id: str,
    db: Session = Depends(get_db)
):
    """Получение полного трейса по request_id"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Получаем все спаны для request_id
        trace_spans = db.query(TraceEntryDB).filter(
            TraceEntryDB.request_id == request_id
        ).order_by(TraceEntryDB.start_time).all()

        if not trace_spans:
            raise HTTPException(status_code=404, detail="Request trace not found")

        # Используем trace_id из первого спана
        trace_id = trace_spans[0].trace_id

        # Получаем все ошибки для этого request_id
        trace_errors = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.request_id == request_id
        ).order_by(ErrorEntryDB.timestamp).all()

        # Определяем метаданные
        first_span = trace_spans[0]
        user_id = first_span.user_id
        session_id = first_span.session_id

        # Вычисляем общее время выполнения
        start_time = min(span.start_time for span in trace_spans)
        end_times = [span.end_time for span in trace_spans if span.end_time]
        end_time = max(end_times) if end_times else None
        total_duration = (end_time - start_time).total_seconds() * 1000 if end_time else None

        # Определяем общий статус
        has_errors = any(span.status == "error" for span in trace_spans)
        status = "error" if has_errors else "success"

        # Формируем путь через сервисы
        services_path = []
        for span in trace_spans:
            service_info = {
                "service": span.service,
                "operation": span.operation,
                "start_time": span.start_time.isoformat(),
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration": span.duration,
                "status": span.status,
                "error_message": span.error_message,
                "metadata": span.trace_metadata
            }
            services_path.append(service_info)

        # Формируем информацию об ошибках
        errors = []
        for error in trace_errors:
            error_info = {
                "service": error.service,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "category": error.category,
                "timestamp": error.timestamp.isoformat(),
                "stack_trace": error.stack_trace,
                "context": error.context
            }
            errors.append(error_info)

        return FullTraceResponse(
            request_id=request_id,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            total_duration=total_duration,
            status=status,
            services_path=services_path,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get full request trace {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get full request trace: {str(e)}")


@app.get("/metrics/traces/count")
async def get_traces_count(
    service: str = None,
    status: str = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить количество трейсов по времени для графиков"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        query = db.query(
            TraceEntryDB.start_time,
            TraceEntryDB.status,
            TraceEntryDB.service
        ).filter(TraceEntryDB.start_time >= start_time)

        if service:
            query = query.filter(TraceEntryDB.service == service)
        if status:
            query = query.filter(TraceEntryDB.status == status)

        results = query.order_by(TraceEntryDB.start_time).all()

        # Группируем по часам
        hourly_data = {}
        for trace in results:
            hour = trace.start_time.replace(minute=0, second=0, microsecond=0)
            key = f"{trace.service}_{trace.status}_{hour.isoformat()}"

            if key not in hourly_data:
                hourly_data[key] = {
                    "timestamp": hour.isoformat(),
                    "service": trace.service,
                    "status": trace.status,
                    "count": 0
                }
            hourly_data[key]["count"] += 1

        return list(hourly_data.values())

    except Exception as e:
        logger.error(f"Failed to get traces count: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get traces count: {str(e)}")


@app.get("/metrics/errors/count")
async def get_errors_count(
    service: str = None,
    error_type: str = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить количество ошибок по времени для графиков"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        query = db.query(
            ErrorEntryDB.timestamp,
            ErrorEntryDB.error_type,
            ErrorEntryDB.service
        ).filter(ErrorEntryDB.timestamp >= start_time)

        if service:
            query = query.filter(ErrorEntryDB.service == service)
        if error_type:
            query = query.filter(ErrorEntryDB.error_type == error_type)

        results = query.order_by(ErrorEntryDB.timestamp).all()

        # Группируем по часам
        hourly_data = {}
        for error in results:
            hour = error.timestamp.replace(minute=0, second=0, microsecond=0)
            key = f"{error.service}_{error.error_type}_{hour.isoformat()}"

            if key not in hourly_data:
                hourly_data[key] = {
                    "timestamp": hour.isoformat(),
                    "service": error.service,
                    "error_type": error.error_type,
                    "count": 0
                }
            hourly_data[key]["count"] += 1

        return list(hourly_data.values())

    except Exception as e:
        logger.error(f"Failed to get errors count: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get errors count: {str(e)}")


@app.get("/metrics/performance")
async def get_performance_metrics(
    service: str = None,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить метрики производительности"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        query = db.query(
            TraceEntryDB.start_time,
            TraceEntryDB.duration,
            TraceEntryDB.service,
            TraceEntryDB.operation
        ).filter(
            TraceEntryDB.start_time >= start_time,
            TraceEntryDB.duration.isnot(None)
        )

        if service:
            query = query.filter(TraceEntryDB.service == service)

        results = query.order_by(TraceEntryDB.start_time).all()

        # Группируем по часам и вычисляем среднее время
        hourly_data = {}
        for trace in results:
            hour = trace.start_time.replace(minute=0, second=0, microsecond=0)

            if trace.service not in hourly_data:
                hourly_data[trace.service] = {}

            if hour.isoformat() not in hourly_data[trace.service]:
                hourly_data[trace.service][hour.isoformat()] = {
                    "timestamp": hour.isoformat(),
                    "service": trace.service,
                    "avg_duration": 0,
                    "min_duration": float('inf'),
                    "max_duration": 0,
                    "count": 0,
                    "total_duration": 0
                }

            data = hourly_data[trace.service][hour.isoformat()]
            data["count"] += 1
            data["total_duration"] += trace.duration
            data["avg_duration"] = data["total_duration"] / data["count"]
            data["min_duration"] = min(data["min_duration"], trace.duration)
            data["max_duration"] = max(data["max_duration"], trace.duration)

        # Преобразуем в плоский список
        flat_data = []
        for service_data in hourly_data.values():
            for hour_data in service_data.values():
                flat_data.append(hour_data)

        return flat_data

    except Exception as e:
        logger.error(f"Failed to get performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@app.get("/metrics/services/summary")
async def get_services_summary(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить сводку по сервисам"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        # Статистика трейсов по сервисам
        traces_stats = db.query(
            TraceEntryDB.service,
            TraceEntryDB.status,
            func.count(TraceEntryDB.id).label('count')
        ).filter(
            TraceEntryDB.start_time >= start_time
        ).group_by(
            TraceEntryDB.service,
            TraceEntryDB.status
        ).all()

        # Статистика ошибок по сервисам
        errors_stats = db.query(
            ErrorEntryDB.service,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.service).all()

        # Агрегируем данные
        services = {}

        for stat in traces_stats:
            if stat.service not in services:
                services[stat.service] = {
                    "service": stat.service,
                    "total_traces": 0,
                    "success_traces": 0,
                    "error_traces": 0,
                    "total_errors": 0
                }

            services[stat.service]["total_traces"] += stat.count
            if stat.status == "success":
                services[stat.service]["success_traces"] += stat.count
            elif stat.status == "error":
                services[stat.service]["error_traces"] += stat.count

        for stat in errors_stats:
            if stat.service not in services:
                services[stat.service] = {
                    "service": stat.service,
                    "total_traces": 0,
                    "success_traces": 0,
                    "error_traces": 0,
                    "total_errors": 0
                }
            services[stat.service]["total_errors"] = stat.count

        return list(services.values())

    except Exception as e:
        logger.error(f"Failed to get services summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get services summary: {str(e)}")


@app.get("/security/violations")
async def get_security_violations(
    hours: int = 24,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Получить нарушения безопасности"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        # Получаем нарушения безопасности
        violations = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.category == "security",
            ErrorEntryDB.timestamp >= start_time
        ).order_by(ErrorEntryDB.timestamp.desc()).limit(limit).offset(offset).all()

        return [
            {
                "id": violation.id,
                "trace_id": violation.trace_id,
                "request_id": violation.request_id,
                "service": violation.service,
                "error_type": violation.error_type,
                "error_message": violation.error_message,
                "context": violation.context,
                "timestamp": violation.timestamp,
                "user_id": violation.user_id,
                "session_id": violation.session_id,
                "created_at": violation.created_at
            }
            for violation in violations
        ]

    except Exception as e:
        logger.error(f"Failed to get security violations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get security violations: {str(e)}")


@app.get("/security/violations/stats")
async def get_security_violations_stats(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить статистику нарушений безопасности"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        # Общее количество нарушений
        total_violations = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.category == "security",
            ErrorEntryDB.timestamp >= start_time
        ).count()

        # Нарушения по типам
        violations_by_type = db.query(
            ErrorEntryDB.error_type,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.category == "security",
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.error_type).all()

        # Нарушения по сервисам
        violations_by_service = db.query(
            ErrorEntryDB.service,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.category == "security",
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.service).all()

        # Нарушения по часам
        hourly_violations = db.query(
            func.date_trunc('hour', ErrorEntryDB.timestamp).label('hour'),
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.category == "security",
            ErrorEntryDB.timestamp >= start_time
        ).group_by(
            func.date_trunc('hour', ErrorEntryDB.timestamp)
        ).order_by('hour').all()

        return {
            "total_violations": total_violations,
            "violations_by_type": [
                {"error_type": v.error_type, "count": v.count}
                for v in violations_by_type
            ],
            "violations_by_service": [
                {"service": v.service, "count": v.count}
                for v in violations_by_service
            ],
            "hourly_violations": [
                {"hour": v.hour.isoformat(), "count": v.count}
                for v in hourly_violations
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get security violations stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get security violations stats: {str(e)}")


@app.get("/errors/technical")
async def get_technical_errors(
    hours: int = 24,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Получить технические ошибки"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        # Получаем технические ошибки
        errors = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.category == "technical",
            ErrorEntryDB.timestamp >= start_time
        ).order_by(ErrorEntryDB.timestamp.desc()).limit(limit).offset(offset).all()

        return [
            {
                "id": error.id,
                "trace_id": error.trace_id,
                "request_id": error.request_id,
                "service": error.service,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "stack_trace": error.stack_trace,
                "context": error.context,
                "timestamp": error.timestamp,
                "user_id": error.user_id,
                "session_id": error.session_id,
                "created_at": error.created_at
            }
            for error in errors
        ]

    except Exception as e:
        logger.error(f"Failed to get technical errors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get technical errors: {str(e)}")


@app.get("/errors/stats")
async def get_errors_stats(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """Получить статистику ошибок"""
    if not db_initialized:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        start_time = datetime.now() - timedelta(hours=hours)

        # Общее количество ошибок
        total_errors = db.query(ErrorEntryDB).filter(
            ErrorEntryDB.timestamp >= start_time
        ).count()

        # Ошибки по категориям
        errors_by_category = db.query(
            ErrorEntryDB.category,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.category).all()

        # Ошибки по типам
        errors_by_type = db.query(
            ErrorEntryDB.error_type,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.error_type).all()

        # Ошибки по сервисам
        errors_by_service = db.query(
            ErrorEntryDB.service,
            func.count(ErrorEntryDB.id).label('count')
        ).filter(
            ErrorEntryDB.timestamp >= start_time
        ).group_by(ErrorEntryDB.service).all()

        return {
            "total_errors": total_errors,
            "errors_by_category": [
                {"category": e.category, "count": e.count}
                for e in errors_by_category
            ],
            "errors_by_type": [
                {"error_type": e.error_type, "count": e.count}
                for e in errors_by_type
            ],
            "errors_by_service": [
                {"service": e.service, "count": e.count}
                for e in errors_by_service
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get errors stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get errors stats: {str(e)}")


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


