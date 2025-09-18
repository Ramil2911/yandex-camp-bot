# Common Components

Общие компоненты микросервисной архитектуры.

## Структура

```
common/
├── llm/                    # LLM компоненты
│   ├── __init__.py
│   └── llm_base.py         # Базовый класс для всех LLM
├── models/                 # Общие модели данных
│   ├── __init__.py
│   └── common.py           # LogEntry, HealthCheckResponse, etc.
├── config.py              # Общие настройки (Settings)
└── utils/                  # Утилиты
    ├── __init__.py
    ├── logging_utils.py    # Логирование
    └── http_client.py      # HTTP клиент для межсервисного взаимодействия
```

## LLM Base Class

### Использование

```python
from common.llm import LLMBase

class MyLLMService(LLMBase):
    def __init__(self, folder_id, openai_api_key):
        super().__init__(
            folder_id=folder_id,
            openai_api_key=openai_api_key,
            component_name="my-service"
        )

    def process_request(self, text, user_id, session_id):
        # Реализация специфичной логики
        pass
```

## Общие модели

### LogEntry
```python
from common.models import LogEntry

log_entry = LogEntry(
    level="INFO",
    service="my-service",
    message="Operation completed",
    user_id="user123",
    session_id="session456"
)
```

### HealthCheckResponse
```python
from common.models import HealthCheckResponse

response = HealthCheckResponse(
    status="healthy",
    service="my-service",
    timestamp="2024-01-01T00:00:00Z",
    stats={"requests": 100}
)
```

## Утилиты

### Логирование
```python
from common.utils import setup_logging, log_service_event

logger = setup_logging("my-service")
log_service_event("my-service", "operation_started", "Processing request")
```

### HTTP клиент
```python
from common.utils import service_http_client

response = await service_http_client.get("http://other-service/health")
```

## Конфигурация

### Common Settings
```python
from common.config import config

# Использование общих настроек
model_config = config.model_config
redis_url = config.redis_url
```
