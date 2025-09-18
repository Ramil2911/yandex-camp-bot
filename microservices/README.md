# Микросервисная архитектура Telegram бота

Проект представляет собой Telegram бота с RAG-системой, разделенный на независимые микросервисы с общими компонентами.

## Архитектура

```
┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │────│  Telegram Bot   │
│    (Port 8000)  │    └─────────────────┘
└─────────────────┘
          │
    ┌─────┼─────────────────────┐
    │     │                     │
    ▼     ▼                     ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Security   │ │     RAG     │ │  Dialogue   │
│  Service    │ │   Service   │ │  Service   │
│  (Port 8001)│ │  (Port 8002)│ │  (Port 8003)│
└─────────────┘ └─────────────┘ └─────────────┘
    │     │                     │
    └─────┼─────────────────────┘
          ▼
    ┌─────────────┐
    │ Monitoring  │
    │   Service   │
    │  (Port 8004)│
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │   Common    │
    │ Components  │
    └─────────────┘
```

## Сервисы

### 1. API Gateway Service
**Порт:** 8000
- **Функция:** Входная точка, маршрутизация запросов
- **Технологии:** FastAPI, python-telegram-bot

### 2. Security Service
**Порт:** 8001
- **Функция:** Модерация и безопасность запросов
- **Технологии:** FastAPI, YandexGPT, эвристики

### 3. RAG Service
**Порт:** 8002
- **Функция:** Поиск и извлечение информации из документов
- **Технологии:** FastAPI, ChromaDB, LangChain, Sentence Transformers

### 4. Dialogue Service
**Порт:** 8003
- **Функция:** Диалоговый ИИ с поддержкой контекста
- **Технологии:** FastAPI, LangChain, YandexGPT

### 5. Monitoring Service
**Порт:** 8004
- **Функция:** Централизованное логирование и мониторинг всех сервисов
- **Технологии:** FastAPI, PostgreSQL, SQLAlchemy
- **База данных:** PostgreSQL для хранения логов, метрик и статистики

### 6. Вспомогательные сервисы

#### PostgreSQL Database
**Порт:** 5432
- **Функция:** Хранение логов и метрик от всех сервисов
- **Назначение:** Monitoring Service сохраняет туда все логи, метрики производительности и статистику использования

#### Redis
**Порт:** 6379
- **Функция:** Кеширование и хранение сессий
- **Назначение:** Быстрое хранение временных данных и состояний

### 7. Common Components
**Функция:** Общие компоненты для всех сервисов
- **LLM Base:** Базовый класс для всех LLM компонентов
- **Common Models:** Общие модели данных (LogEntry, HealthCheckResponse)
- **Utils:** Утилиты для логирования и HTTP взаимодействия
- **Config:** Общие настройки

## Быстрый запуск

1. **Настройка переменных окружения:**
```bash
cp env.example .env
# Отредактируйте .env файл с вашими API ключами
```

2. **Запуск всех сервисов:**
```bash
docker-compose up --build
```

3. **Или запуск отдельных сервисов:**
```bash
# API Gateway
cd api-gateway && pip install -r requirements.txt && uvicorn app.main:app --port 8000

# Security Service
cd security-service && pip install -r requirements.txt && uvicorn app.main:app --port 8001

# RAG Service
cd rag-service && pip install -r requirements.txt && uvicorn app.main:app --port 8002

# Dialogue Service
cd dialogue-service && pip install -r requirements.txt && uvicorn app.main:app --port 8003

# Monitoring Service
cd monitoring-service && pip install -r requirements.txt && uvicorn app.main:app --port 8004
```

## Конфигурация

### Обязательные переменные окружения:

```bash
# API ключи
YC_OPENAI_TOKEN=your_yandex_openai_token_here
YC_FOLDER_ID=your_yandex_folder_id_here
TG_BOT_TOKEN=your_telegram_bot_token_here

# База данных PostgreSQL
POSTGRES_DB=monitoring           # Имя базы данных для логов и метрик
POSTGRES_USER=user               # Пользователь базы данных
POSTGRES_PASSWORD=password       # Пароль пользователя базы данных
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

#### 🔐 **Безопасность кредов PostgreSQL:**

- **`POSTGRES_USER`** и **`POSTGRES_PASSWORD`** используются для аутентификации в базе данных
- Эти креды **не должны** совпадать с вашими реальными учетными данными
- В продакшене используйте **сильные, уникальные пароли**
- DATABASE_URL автоматически формируется из отдельных переменных

### Структура данных:

```
microservices/
├── api-gateway/          # API Gateway Service
├── security-service/     # Security Service
├── rag-service/          # RAG Service
├── dialogue-service/     # Dialogue Service
├── monitoring-service/   # Monitoring Service
├── docker-compose.yml    # Оркестрация
├── env.example          # Пример конфигурации
└── README.md            # Эта документация
```

## Мониторинг и логирование

- Все сервисы отправляют логи в Monitoring Service
- Доступна панель здоровья: `GET /health` на каждом сервисе
- Статистика доступна по `GET /stats`

## Масштабируемость

- Каждый сервис может быть масштабирован независимо
- Используется HTTP для межсервисного взаимодействия
- Готова к развертыванию в Kubernetes

## Безопасность

- Многоуровневая система безопасности
- Эвристическая фильтрация + LLM-модерация
- Логирование всех действий пользователей

## Разработка

Для добавления нового функционала:

1. Создайте отдельный сервис если функция независима
2. Добавьте endpoints в существующие сервисы если функция связана
3. Обновите docker-compose.yml
4. Добавьте переменные окружения в env.example
