from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .config import settings

# Создание engine
engine = create_engine(settings.database_url, echo=False)

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
    """Инициализация базы данных"""
    try:
        create_tables()
        return True
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        return False


# Инициализация при импорте
if __name__ != "__main__":
    init_db()
