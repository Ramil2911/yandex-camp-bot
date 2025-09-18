"""
Конфигурация RAG системы
"""

# Настройки RAG
RAG_CONFIG = {
    "enabled": True,
    "persist_directory": "./chroma_db",
    "data_directory": "./data",
    "max_documents": 3,
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "embedding_model": "all-MiniLM-L6-v2",
    "similarity_threshold": 0.6,  # Порог схожести для фильтрации (0.0-1.0)
    "min_documents": 1,  # Минимальное количество документов для возврата
    "max_search_results": 5  # Максимальное количество результатов для поиска перед фильтрацией
}

# Настройки эмбеддингов
EMBEDDING_CONFIG = {
    "model_name": "all-MiniLM-L6-v2",
    "model_kwargs": {"device": "cpu"},
    "encode_kwargs": {"normalize_embeddings": True}
}

# Настройки текстового сплиттера
TEXT_SPLITTER_CONFIG = {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "length_function": len,
    "separators": ["\n\n", "\n", " ", ""]
}

# Настройки векторной БД
VECTORSTORE_CONFIG = {
    "persist_directory": "./chroma_db",
    "collection_name": "documents"
}
