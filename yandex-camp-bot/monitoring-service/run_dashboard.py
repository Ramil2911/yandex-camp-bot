#!/usr/bin/env python3
"""
Скрипт для запуска Streamlit дашборда мониторинга
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Запуск Streamlit дашборда"""
    
    # Определяем путь к дашборду
    dashboard_path = Path(__file__).parent / "app" / "dashboard.py"
    
    if not dashboard_path.exists():
        print(f"❌ Файл дашборда не найден: {dashboard_path}")
        sys.exit(1)
    
    print("🚀 Запуск Streamlit дашборда мониторинга...")
    print(f"📁 Путь к дашборду: {dashboard_path}")
    print("🌐 Дашборд будет доступен по адресу: http://localhost:8501")
    print("📊 URL мониторинг сервиса: http://localhost:8004")
    print("=" * 60)
    
    try:
        # Запускаем Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Дашборд остановлен пользователем")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска дашборда: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
