# Security Service

Сервис модерации и безопасности для проверки пользовательских запросов.

## Функциональность

- **LLM-модерация**: Проверка запросов через YandexGPT
- **Эвристическая фильтрация**: Быстрая проверка на подозрительные слова
- **Многоуровневая безопасность**: Комбинация разных подходов

## API Endpoints

### Основные
- `POST /moderate` - Модерация сообщения
- `GET /health` - Проверка здоровья
- `GET /stats` - Статистика модерации

## Конфигурация

```bash
YC_OPENAI_TOKEN=your_yandex_openai_token
YC_FOLDER_ID=your_yandex_folder_id
MONITORING_SERVICE_URL=http://monitoring-service:8004
```

## Запуск

```bash
cd security-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```
