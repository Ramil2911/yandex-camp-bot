import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Service URLs
    monitoring_service_url: str = os.getenv("MONITORING_SERVICE_URL", "http://monitoring-service:8004")

    # Data directories
    data_directory: str = "/app/data"
    chroma_db_directory: str = "/app/chroma_db"

    # RAG Configuration
    rag_config = {
        "enabled": True,
        "max_documents": 3,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "embedding_model": "all-MiniLM-L6-v2",
        "similarity_threshold": 0.6,
        "min_documents": 1,
        "max_search_results": 5,
        "collection_name": "documents"
    }

    # Embedding Configuration
    embedding_config = {
        "model_name": "all-MiniLM-L6-v2",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True}
    }

    # Text Splitter Configuration
    text_splitter_config = {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "length_function": len,
        "separators": ["\n\n", "\n", " ", ""]
    }


settings = Settings()
