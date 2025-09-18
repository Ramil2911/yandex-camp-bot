#!/bin/bash

# Скрипт для запуска микросервисов
echo "🚀 Запуск микросервисной архитектуры Telegram бота"

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден. Скопируйте env.example в .env и настройте переменные окружения."
    exit 1
fi

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker для запуска сервисов."
    exit 1
fi

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose для запуска сервисов."
    exit 1
fi

echo "📋 Проверка конфигурации..."

# Проверка наличия необходимых переменных окружения
required_vars=("YC_OPENAI_TOKEN" "YC_FOLDER_ID" "TG_BOT_TOKEN" "POSTGRES_DB" "POSTGRES_USER" "POSTGRES_PASSWORD")

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        echo "❌ Переменная $var не найдена в .env файле"
        exit 1
    fi
done

echo "✅ Конфигурация проверена"

# Создание необходимых директорий
echo "📁 Создание директорий..."
mkdir -p ../data
mkdir -p ../logs

# Запуск сервисов
echo "🐳 Запуск Docker Compose..."
docker-compose up --build -d

echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Проверка здоровья сервисов
echo "🏥 Проверка здоровья сервисов..."

services=("api-gateway:8000" "security-service:8001" "rag-service:8002" "dialogue-service:8003" "monitoring-service:8004")

for service in "${services[@]}"; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)

    if curl -f http://localhost:$port/health &>/dev/null; then
        echo "✅ $name: здоров"
    else
        echo "❌ $name: проблемы со здоровьем"
    fi
done

echo ""
echo "🎉 Микросервисы запущены!"
echo ""
echo "📊 Доступные сервисы:"
echo "  🌐 API Gateway:    http://localhost:8000"
echo "  🔒 Security:       http://localhost:8001"
echo "  📚 RAG:           http://localhost:8002"
echo "  💬 Dialogue:      http://localhost:8003"
echo "  📈 Monitoring:    http://localhost:8004"
echo ""
echo "🛑 Для остановки выполните: docker-compose down"
echo "📜 Для просмотра логов: docker-compose logs -f"
