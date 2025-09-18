# API Gateway Service

Входная точка микросервисной архитектуры Telegram бота.

## Функциональность

- **Telegram интеграция**: Прием сообщений от Telegram Bot API
- **Маршрутизация**: Распределение запросов между сервисами
- **Безопасность**: Интеграция с Security Service
- **Логирование**: Отправка логов в Monitoring Service

## API Endpoints

### Основные
- `GET /` - Информация о сервисе
- `GET /health` - Проверка здоровья

## Конфигурация

Сервис использует переменные окружения:

```bash
TELEGRAM_TOKEN=your_telegram_bot_token
SECURITY_SERVICE_URL=http://security-service:8001
RAG_SERVICE_URL=http://rag-service:8002
DIALOGUE_SERVICE_URL=http://dialogue-service:8003
MONITORING_SERVICE_URL=http://monitoring-service:8004
```

## Запуск

```bash
cd api-gateway
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Зависимости

- Security Service
- RAG Service
- Dialogue Service
- Monitoring Service
