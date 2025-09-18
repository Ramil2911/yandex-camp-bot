# RAG (Retrieval-Augmented Generation) модуль

Модуль RAG для Telegram бота, обеспечивающий поиск релевантной информации и формирование контекста для LLM.

## Структура модуля

```
app/rag/
├── __init__.py          # Экспорт основных компонентов
├── rag_config.py        # Конфигурация RAG системы
├── rag_system.py        # Базовая RAG система
├── rag_adapter.py       # Адаптер для интеграции с ботом
├── rag_utils.py         # Утилиты для работы с RAG
└── README.md           # Документация модуля
```

## Компоненты

### 1. RAGSystem (`rag_system.py`)
Базовая система для работы с документами и векторным поиском:
- Загрузка документов из директории
- Создание эмбеддингов
- Векторный поиск релевантных документов
- Управление векторной БД

### 2. RAGAdapter (`rag_adapter.py`)
Адаптер для интеграции с диалоговым ботом:
- Поиск релевантного контекста
- Форматирование промптов с контекстом
- Статистика и мониторинг
- Управление состоянием RAG

### 3. Конфигурация (`rag_config.py`)
Настройки RAG системы:
- Параметры эмбеддингов
- Настройки текстового сплиттера
- Конфигурация векторной БД
- Основные параметры RAG

### 4. Утилиты (`rag_utils.py`)
Вспомогательные функции:
- Создание RAG адаптера
- Валидация директорий
- Тестирование системы
- Проверка здоровья RAG

## Использование

### Базовое использование
```python
from app.rag import RAGAdapter

# Создание адаптера
rag = RAGAdapter()

# Обработка запроса с RAG
result = await rag.process_with_rag("Ваш вопрос")
```

### Расширенное использование
```python
from app.rag import RAGAdapter, RAG_CONFIG
from app.rag.rag_utils import test_rag_system

# Создание с кастомными настройками
rag = RAGAdapter(
    persist_directory="./custom_db",
    data_directory="./custom_data",
    enabled=True
)

# Тестирование системы
test_results = await test_rag_system()
```

## Конфигурация

Основные настройки в `rag_config.py`:

```python
RAG_CONFIG = {
    "enabled": True,                    # Включить/выключить RAG
    "persist_directory": "./chroma_db", # Директория векторной БД
    "data_directory": "./data",         # Директория с документами
    "max_documents": 3,                 # Максимум документов для контекста
    "chunk_size": 1000,                 # Размер чанков текста
    "chunk_overlap": 200,               # Перекрытие между чанками
    "embedding_model": "all-MiniLM-L6-v2", # Модель эмбеддингов
    "similarity_threshold": 0.7         # Порог схожести
}
```

## API

### RAGAdapter

#### Основные методы:
- `process_with_rag(query, max_docs)` - обработка запроса с RAG
- `get_relevant_context(query, max_docs)` - поиск релевантного контекста
- `get_rag_stats()` - получение статистики
- `toggle_rag(enabled)` - включение/отключение RAG
- `reload_documents()` - перезагрузка документов

#### Свойства:
- `enabled` - статус RAG системы
- `stats` - статистика использования

### RAGSystem

#### Основные методы:
- `load_documents(directory)` - загрузка документов
- `add_documents()` - добавление в векторную БД
- `search_relevant_docs(query, k)` - поиск документов
- `get_document_count()` - количество документов
- `get_vectorstore_info()` - информация о векторной БД

## Мониторинг

### Статистика
RAG система отслеживает:
- Количество запросов к RAG
- Успешные поиски
- Ошибки
- Количество загруженных документов
- Среднюю длину контекста

### Проверка здоровья
```python
from app.rag.rag_utils import get_rag_health_status

health = get_rag_health_status(rag_adapter)
print(f"Здоровье системы: {health['healthy']}")
print(f"Проблемы: {health['issues']}")
```

## Логирование

Все события RAG логируются с помощью loguru:
- Инициализация компонентов
- Загрузка документов
- Поиск релевантных документов
- Ошибки и предупреждения

## Требования

- Python >= 3.13
- langchain-community
- chromadb
- sentence-transformers
- loguru

## Примеры

### Добавление новых документов
1. Поместите `.txt` файлы в `./data/`
2. Перезапустите бота или вызовите `reload_documents()`

### Отключение RAG
```python
rag_adapter.toggle_rag(False)
```

### Получение статистики
```python
stats = rag_adapter.get_rag_stats()
print(f"Запросов: {stats['rag_queries']}")
print(f"Успешность: {stats['success_rate']:.1%}")
```
