# Dialogue Service

Сервис диалогового ИИ с поддержкой контекста и памяти разговоров.

## Функциональность

- **Диалоговый ИИ**: Обработка запросов через YandexGPT
- **Управление памятью**: Сохранение истории разговоров
- **Контекстное обогащение**: Интеграция с RAG для улучшения ответов

## API Endpoints

### Основные
- `POST /dialogue` - Обработка диалогового запроса
- `POST /clear-memory` - Очистка памяти сессии
- `GET /session/{session_id}` - Информация о сессии

## Особенности

- **Многосессионность**: Поддержка одновременных разговоров
- **Контекст**: Использование RAG для обогащения ответов
- **Очистка памяти**: Возможность сброса истории разговора

## Конфигурация

```bash
YC_OPENAI_TOKEN=your_yandex_openai_token
YC_FOLDER_ID=your_yandex_folder_id
RAG_SERVICE_URL=http://rag-service:8002
MONITORING_SERVICE_URL=http://monitoring-service:8004
```

## Запуск

```bash
cd dialogue-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003
```
