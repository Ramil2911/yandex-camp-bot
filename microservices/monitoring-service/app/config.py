import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/monitoring")

    # Monitoring Configuration
    monitoring_config = {
        "log_retention_days": 30,
        "max_logs_per_request": 1000,
        "enable_metrics": True,
        "metrics_retention_hours": 24
    }

    # Log levels mapping
    log_levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }


settings = Settings()
