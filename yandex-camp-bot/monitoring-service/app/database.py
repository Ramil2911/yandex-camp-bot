from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from common.config import config

# Создание engine
engine = create_engine(config.database_url, echo=False)

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


class LogEntryDB(Base):
    """Модель для хранения логов"""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), index=True)
    service = Column(String(100), index=True)
    message = Column(Text)
    user_id = Column(String(100), index=True, nullable=True)
    session_id = Column(String(100), index=True, nullable=True)
    extra = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MetricsEntryDB(Base):
    """Модель для хранения метрик"""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(100), index=True)
    metric_name = Column(String(200), index=True)
    value = Column(Float)
    tags = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ServiceHealthDB(Base):
    """Модель для хранения статуса сервисов"""
    __tablename__ = "service_health"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), unique=True, index=True)
    status = Column(String(20))
    last_check = Column(DateTime, default=datetime.utcnow)
    response_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TraceEntryDB(Base):
    """Модель для хранения трейсов"""
    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(100), index=True)
    request_id = Column(String(100), index=True)
    span_id = Column(String(100), index=True)
    service = Column(String(100), index=True)
    operation = Column(String(200), index=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String(20), index=True)
    error_message = Column(Text, nullable=True)
    trace_metadata = Column(JSON, nullable=True)
    user_id = Column(String(100), index=True, nullable=True)
    session_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ErrorEntryDB(Base):
    """Модель для хранения детальной информации об ошибках"""
    __tablename__ = "errors"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(100), index=True)
    request_id = Column(String(100), index=True)
    service = Column(String(100), index=True)
    error_type = Column(String(100), index=True)
    error_message = Column(Text)
    stack_trace = Column(Text, nullable=True)
    context = Column(JSON, nullable=True)
    timestamp = Column(DateTime, index=True)
    user_id = Column(String(100), index=True, nullable=True)
    session_id = Column(String(100), index=True, nullable=True)
    category = Column(String(20), default="technical", index=True)  # "security" или "technical"
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    """Генератор сессий базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Создание таблиц в базе данных"""
    Base.metadata.create_all(bind=engine)


def init_db():
    """Инициализация базы данных с retry логикой"""
    import time
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Проверяем подключение
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Создаем таблицы
            create_tables()
            print("Database initialized successfully")
            return True
        except Exception as e:
            print(f"Database init attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("All database initialization attempts failed")
                return False


# Инициализация при импорте
if __name__ != "__main__":
    init_db()
