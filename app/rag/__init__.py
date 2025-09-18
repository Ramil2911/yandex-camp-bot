"""
RAG (Retrieval-Augmented Generation) модуль для Telegram бота.
Обеспечивает поиск релевантной информации и формирование контекста для LLM.
"""

from .rag_system import RAGSystem
from .rag_adapter import RAGAdapter
from .rag_config import RAG_CONFIG

__all__ = [
    "RAGSystem",
    "RAGAdapter", 
    "RAG_CONFIG"
]
