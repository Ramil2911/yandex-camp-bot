#!/bin/bash

# Скрипт для тестирования сборки Docker образов
echo "🔧 Тестирование сборки микросервисов"

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создаю из примера..."
    cp env.example .env
    echo "✅ Создан .env файл. Не забудьте заполнить API ключи!"
fi

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

echo "🐳 Сборка Docker образов..."

# Сборка образов по одному для лучшей диагностики
services=("api-gateway" "security-service" "rag-service" "dialogue-service" "monitoring-service")

for service in "${services[@]}"; do
    echo "📦 Сборка $service..."
    if docker-compose build $service; then
        echo "✅ $service собран успешно"
    else
        echo "❌ Ошибка сборки $service"
        exit 1
    fi
done

echo ""
echo "🎉 Все образы собраны успешно!"
echo ""
echo "🚀 Запуск сервисов: docker-compose up -d"
echo "🛑 Остановка: docker-compose down"
echo "📜 Логи: docker-compose logs -f"
