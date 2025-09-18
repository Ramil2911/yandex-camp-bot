#!/usr/bin/env python3
"""
Скрипт миграции базы данных для добавления поля category в таблицу errors
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Добавляем путь к модулю common
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.config import config

def migrate_database():
    """Выполнить миграцию базы данных"""

    # Создаем engine
    engine = create_engine(config.database_url, echo=True)

    try:
        with engine.connect() as conn:
            print("🔄 Начинаем миграцию базы данных...")

            # Проверяем, существует ли уже колонка category
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'errors' AND column_name = 'category'
            """))

            if result.fetchone():
                print("✅ Колонка 'category' уже существует. Миграция не требуется.")
                return

            # Добавляем колонку category
            print("📝 Добавляем колонку 'category' в таблицу 'errors'...")
            conn.execute(text("""
                ALTER TABLE errors
                ADD COLUMN category VARCHAR(20) DEFAULT 'technical'
            """))

            # Обновляем существующие записи, классифицируя их
            print("🔍 Классифицируем существующие ошибки...")
            conn.execute(text("""
                UPDATE errors
                SET category = 'security'
                WHERE LOWER(error_type || ' ' || error_message) LIKE LOWER('%unauthorized%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%forbidden%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%authentication%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%permission%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%access denied%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%security%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%auth%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%login%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%password%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%token%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%403%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%401%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%rate limit%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%suspicious%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%malicious%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%attack%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%intrusion%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%sql injection%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%xss%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%csrf%')
                   OR LOWER(error_type || ' ' || error_message) LIKE LOWER('%brute force%')
            """))

            conn.commit()
            print("✅ Миграция успешно завершена!")

            # Проверяем результат
            result = conn.execute(text("SELECT COUNT(*) FROM errors WHERE category = 'security'"))
            security_count = result.fetchone()[0]

            result = conn.execute(text("SELECT COUNT(*) FROM errors WHERE category = 'technical'"))
            technical_count = result.fetchone()[0]

            print(f"📊 Результаты классификации:")
            print(f"   Security ошибок: {security_count}")
            print(f"   Технических ошибок: {technical_count}")

    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Запуск миграции базы данных monitoring service")
    migrate_database()
    print("✨ Миграция завершена!")
