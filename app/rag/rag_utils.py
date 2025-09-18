"""
Утилиты для работы с RAG системой
"""

import os
import asyncio
from typing import List, Dict, Any
from loguru import logger

from .rag_system import RAGSystem
from .rag_adapter import RAGAdapter
from .rag_config import RAG_CONFIG


async def create_rag_adapter(persist_directory: str = None, 
                           data_directory: str = None,
                           enabled: bool = None) -> RAGAdapter:
    """
    Создание RAG адаптера с настройками по умолчанию
    
    Args:
        persist_directory: Директория для векторной БД
        data_directory: Директория с документами
        enabled: Включен ли RAG
        
    Returns:
        RAGAdapter: Настроенный адаптер
    """
    return RAGAdapter(
        persist_directory=persist_directory or RAG_CONFIG["persist_directory"],
        data_directory=data_directory or RAG_CONFIG["data_directory"],
        enabled=enabled if enabled is not None else RAG_CONFIG["enabled"]
    )


def validate_data_directory(data_directory: str) -> bool:
    """
    Проверка валидности директории с данными
    
    Args:
        data_directory: Путь к директории
        
    Returns:
        bool: True если директория валидна
    """
    if not os.path.exists(data_directory):
        logger.error(f"Директория {data_directory} не существует")
        return False
    
    if not os.path.isdir(data_directory):
        logger.error(f"{data_directory} не является директорией")
        return False
    
    # Проверяем наличие .txt и .pdf файлов
    txt_files = [f for f in os.listdir(data_directory) if f.endswith('.txt')]
    pdf_files = [f for f in os.listdir(data_directory) if f.endswith('.pdf')]
    
    if not txt_files and not pdf_files:
        logger.warning(f"В директории {data_directory} нет .txt или .pdf файлов")
        return False
    
    logger.info(f"Найдено {len(txt_files)} .txt файлов и {len(pdf_files)} .pdf файлов в {data_directory}")
    return True


def get_data_directory_info(data_directory: str) -> Dict[str, Any]:
    """
    Получение информации о директории с данными
    
    Args:
        data_directory: Путь к директории
        
    Returns:
        Dict: Информация о директории
    """
    info = {
        "exists": False,
        "is_directory": False,
        "txt_files": [],
        "txt_count": 0,
        "pdf_files": [],
        "pdf_count": 0,
        "total_size": 0
    }
    
    if not os.path.exists(data_directory):
        return info
    
    info["exists"] = True
    
    if not os.path.isdir(data_directory):
        return info
    
    info["is_directory"] = True
    
    try:
        files = os.listdir(data_directory)
        txt_files = [f for f in files if f.endswith('.txt')]
        pdf_files = [f for f in files if f.endswith('.pdf')]
        
        info["txt_files"] = txt_files
        info["txt_count"] = len(txt_files)
        info["pdf_files"] = pdf_files
        info["pdf_count"] = len(pdf_files)
        
        # Подсчитываем общий размер
        total_size = 0
        all_files = txt_files + pdf_files
        for file in all_files:
            file_path = os.path.join(data_directory, file)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
        info["total_size"] = total_size
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о директории: {e}")
    
    return info


async def test_rag_system(persist_directory: str = None, 
                         data_directory: str = None) -> Dict[str, Any]:
    """
    Тестирование RAG системы
    
    Args:
        persist_directory: Директория для векторной БД
        data_directory: Директория с документами
        
    Returns:
        Dict: Результаты тестирования
    """
    results = {
        "success": False,
        "error": None,
        "documents_loaded": 0,
        "test_queries": [],
        "stats": {}
    }
    
    try:
        # Создаем RAG систему
        rag_system = RAGSystem(
            persist_directory=persist_directory or RAG_CONFIG["persist_directory"],
            data_directory=data_directory or RAG_CONFIG["data_directory"]
        )
        
        # Загружаем документы
        await rag_system.add_documents()
        results["documents_loaded"] = rag_system.get_document_count()
        
        # Тестовые запросы
        test_queries = [
            "Что такое программирование?",
            "Какие есть типы ИИ?",
            "Как создать бота?",
            "Что такое машинное обучение?"
        ]
        
        for query in test_queries:
            docs = await rag_system.search_relevant_docs(query, k=2)
            results["test_queries"].append({
                "query": query,
                "found_docs": len(docs),
                "success": len(docs) > 0
            })
        
        results["success"] = True
        results["stats"] = rag_system.get_vectorstore_info()
        
    except Exception as e:
        results["error"] = str(e)
        logger.error(f"Ошибка тестирования RAG: {e}")
    
    return results


def cleanup_rag_data(persist_directory: str = None):
    """
    Очистка данных RAG системы
    
    Args:
        persist_directory: Директория с данными RAG
    """
    persist_dir = persist_directory or RAG_CONFIG["persist_directory"]
    
    try:
        if os.path.exists(persist_dir):
            import shutil
            shutil.rmtree(persist_dir)
            logger.info(f"Данные RAG очищены: {persist_dir}")
        else:
            logger.info("Директория RAG не существует, очистка не требуется")
    except Exception as e:
        logger.error(f"Ошибка очистки данных RAG: {e}")


def get_rag_health_status(rag_adapter: RAGAdapter) -> Dict[str, Any]:
    """
    Получение статуса здоровья RAG системы
    
    Args:
        rag_adapter: Адаптер RAG системы
        
    Returns:
        Dict: Статус здоровья
    """
    status = {
        "healthy": False,
        "enabled": rag_adapter.enabled,
        "issues": [],
        "stats": rag_adapter.get_rag_stats()
    }
    
    if not rag_adapter.enabled:
        status["issues"].append("RAG отключен")
        return status
    
    if not rag_adapter.rag_system:
        status["issues"].append("RAG система не инициализирована")
        return status
    
    if rag_adapter.stats["documents_loaded"] == 0:
        status["issues"].append("Нет загруженных документов")
    
    if rag_adapter.stats["rag_errors"] > 0:
        error_rate = rag_adapter.stats["rag_errors"] / max(rag_adapter.stats["rag_queries"], 1)
        if error_rate > 0.1:  # Более 10% ошибок
            status["issues"].append(f"Высокий уровень ошибок: {error_rate:.1%}")
    
    status["healthy"] = len(status["issues"]) == 0
    return status
