import os
import time
import warnings
from typing import List, Optional, Dict, Any
from pathlib import Path
from loguru import logger

from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from .config import settings
from .models import DocumentInfo, RAGSystemInfo

# Подавляем предупреждения
warnings.filterwarnings("ignore", category=DeprecationWarning)


class RAGSystem:
    """RAG система для работы с документами и векторным поиском"""

    def __init__(self):
        self.persist_directory = settings.chroma_db_directory
        self.data_directory = settings.data_directory
        self.documents = []
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None

        # Статистика
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "documents_loaded": 0,
            "last_indexing_time": None
        }

        # Инициализация компонентов
        self._initialize_components()
        self._load_documents()

    def _initialize_components(self):
        """Инициализация компонентов RAG системы"""
        try:
            # Инициализация эмбеддингов
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=settings.embedding_config["model_name"],
                    model_kwargs=settings.embedding_config["model_kwargs"],
                    encode_kwargs=settings.embedding_config["encode_kwargs"]
                )

            # Инициализация текстового сплиттера
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.text_splitter_config["chunk_size"],
                chunk_overlap=settings.text_splitter_config["chunk_overlap"],
                length_function=settings.text_splitter_config["length_function"],
                separators=settings.text_splitter_config["separators"]
            )

            # Инициализация векторной БД
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings,
                    collection_name=settings.rag_config["collection_name"]
                )

            logger.info("RAG components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG components: {e}")
            raise

    def _load_documents(self):
        """Загрузка документов из директории"""
        try:
            data_path = Path(self.data_directory)

            if not data_path.exists():
                logger.warning(f"Data directory {self.data_directory} does not exist")
                return

            # Загрузка TXT файлов
            txt_loader = DirectoryLoader(
                self.data_directory,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            txt_docs = txt_loader.load()
            self.documents.extend(txt_docs)

            # Загрузка PDF файлов
            pdf_loader = DirectoryLoader(
                self.data_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader
            )
            pdf_docs = pdf_loader.load()
            self.documents.extend(pdf_docs)

            self.stats["documents_loaded"] = len(self.documents)
            logger.info(f"Loaded {len(self.documents)} documents from {self.data_directory}")

            # Индексация документов
            if self.documents:
                self._index_documents()

        except Exception as e:
            logger.error(f"Failed to load documents: {e}")

    def _index_documents(self):
        """Индексация документов в векторную БД"""
        try:
            if not self.documents:
                logger.warning("No documents to index")
                return

            # Разделение документов на чанки
            split_docs = self.text_splitter.split_documents(self.documents)

            # Добавление в векторную базу
            self.vectorstore.add_documents(
                documents=split_docs,
                embedding=self.embeddings
            )

            self.stats["last_indexing_time"] = time.time()
            logger.info(f"Indexed {len(split_docs)} document chunks")

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            raise

    async def search_relevant_docs(self, query: str, user_id: str, session_id: str) -> Dict[str, Any]:
        """
        Поиск релевантных документов

        Args:
            query: Поисковый запрос
            user_id: ID пользователя
            session_id: ID сессии

        Returns:
            Dict с результатами поиска
        """
        start_time = time.time()
        self.stats["total_searches"] += 1

        try:
            similarity_threshold = settings.rag_config["similarity_threshold"]
            min_docs = settings.rag_config["min_documents"]
            max_search = settings.rag_config["max_search_results"]

            # Поиск с оценками схожести
            search_k = min(max_search, settings.rag_config["max_documents"] * 3)
            results_with_scores = self.vectorstore.similarity_search_with_score(
                query=query,
                k=search_k
            )

            # Фильтрация по порогу схожести
            filtered_results = []
            similarity_scores = []
            documents_info = []

            for doc, score in results_with_scores:
                # Конвертируем расстояние в схожесть
                similarity = 1 / (1 + score)

                if similarity >= similarity_threshold:
                    filtered_results.append(doc.page_content)
                    similarity_scores.append(similarity)

                    # Информация о документе
                    doc_info = DocumentInfo(
                        filename=getattr(doc, 'metadata', {}).get('source', 'unknown'),
                        content_length=len(doc.page_content),
                        file_type=self._get_file_type(doc.page_content)
                    )
                    documents_info.append(doc_info)

            # Ограничиваем количество результатов
            max_docs = settings.rag_config["max_documents"]
            filtered_results = filtered_results[:max_docs]
            similarity_scores = similarity_scores[:max_docs]
            documents_info = documents_info[:max_docs]

            # Если результатов меньше минимального, возвращаем лучшие
            if len(filtered_results) < min_docs and results_with_scores:
                logger.warning(f"Found only {len(filtered_results)} documents above threshold")
                best_results = []
                best_scores = []
                best_info = []

                for doc, score in results_with_scores[:min_docs]:
                    best_results.append(doc.page_content)
                    best_scores.append(1 / (1 + score))
                    doc_info = DocumentInfo(
                        filename=getattr(doc, 'metadata', {}).get('source', 'unknown'),
                        content_length=len(doc.page_content),
                        file_type=self._get_file_type(doc.page_content)
                    )
                    best_info.append(doc_info)

                filtered_results = best_results
                similarity_scores = best_scores
                documents_info = best_info

            # Объединяем контекст
            context = "\n\n".join(filtered_results) if filtered_results else ""

            search_time = time.time() - start_time
            self.stats["successful_searches"] += 1

            logger.info(
                f"RAG search for user {user_id}: "
                f"found {len(filtered_results)} documents "
                f"(time: {search_time:.2f}s)"
            )

            return {
                "context": context,
                "documents_found": len(filtered_results),
                "search_time": search_time,
                "documents_info": documents_info,
                "similarity_scores": similarity_scores
            }

        except Exception as e:
            search_time = time.time() - start_time
            self.stats["failed_searches"] += 1

            logger.error(
                f"RAG search failed for user {user_id}: {str(e)} "
                f"(time: {search_time:.2f}s)"
            )

            return {
                "context": "",
                "documents_found": 0,
                "search_time": search_time,
                "documents_info": [],
                "similarity_scores": []
            }

    def _get_file_type(self, content: str) -> str:
        """Определение типа файла по содержимому"""
        if "PDF" in content[:100].upper():
            return "pdf"
        return "text"

    def get_system_info(self) -> RAGSystemInfo:
        """Получение информации о RAG системе"""
        try:
            collection = self.vectorstore._collection
            document_count = collection.count() if collection else 0

            return RAGSystemInfo(
                enabled=settings.rag_config["enabled"],
                document_count=document_count,
                collection_name=settings.rag_config["collection_name"],
                last_updated=self.stats["last_indexing_time"],
                stats=self.stats
            )
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return RAGSystemInfo(
                enabled=False,
                document_count=0,
                collection_name="unknown",
                stats=self.stats
            )

    def reload_documents(self):
        """Перезагрузка документов"""
        logger.info("Reloading documents...")
        self.documents = []
        self._load_documents()
        logger.info("Documents reloaded")
