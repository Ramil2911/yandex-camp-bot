import os
import time
import warnings
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from common.config import config
from .models import DocumentInfo, RAGSystemInfo, QueryAnalysisResult
from .query_processor import QueryProcessor

# Подавляем предупреждения
warnings.filterwarnings("ignore", category=DeprecationWarning)


class RAGSystem:
    """RAG система для работы с документами и векторным поиском"""

    def __init__(self):
        self.persist_directory = config.chroma_db_directory
        self.data_directory = config.data_directory
        self.documents = []
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None
        self.query_processor = None

        # Статус инициализации (ленивая инициализация для serverless)
        self.initialization_status = "not_started"
        self.initialization_error = None
        self._initialization_lock = asyncio.Lock()
        self._is_initializing = False

        # Статистика
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "documents_loaded": 0,
            "last_indexing_time": None
        }

        # Пул потоков для ленивой инициализации
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # В serverless не инициализируем сразу - только при первом запросе

    async def _ensure_initialized(self):
        """Ленивая инициализация компонентов при первом обращении"""
        if self.initialization_status == "ready":
            return True
            
        if self.initialization_status == "failed":
            return False
            
        # Используем lock для предотвращения множественной инициализации
        async with self._initialization_lock:
            # Повторная проверка после получения блокировки
            if self.initialization_status == "ready":
                return True
            if self.initialization_status == "failed":
                return False
                
            if self._is_initializing:
                # Ждем завершения инициализации
                while self._is_initializing:
                    await asyncio.sleep(0.1)
                return self.initialization_status == "ready"
            
            self._is_initializing = True
            self.initialization_status = "initializing"
            
            try:
                # Инициализация компонентов в пуле потоков
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, self._initialize_components)
                await loop.run_in_executor(self._executor, self._load_documents)

                # БЕЗОПАСНОСТЬ: QueryProcessor инициализируется при приоритете безопасности
                if config.rag_config.get("security_first", True):
                    self.query_processor = QueryProcessor()
                    logger.info("QueryProcessor initialized for security pipeline")
                else:
                    self.query_processor = None

                self.initialization_status = "ready"
                logger.info("RAG System initialized successfully (lazy)")
                return True

            except Exception as e:
                self.initialization_status = "failed"
                self.initialization_error = str(e)
                logger.error(f"Failed to initialize RAG System: {e}")
                return False
            finally:
                self._is_initializing = False

    def _initialize_components(self):
        """Инициализация компонентов RAG системы (оптимизировано для serverless)"""
        try:
            # Инициализация эмбеддингов с кешированием для serverless
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # Оптимизированные настройки для serverless
                model_kwargs = config.embedding_config["model_kwargs"].copy()
                if config.rag_config.get("serverless_mode", True):
                    # Используем меньше ресурсов в serverless
                    model_kwargs["device"] = "cpu"
                    model_kwargs["trust_remote_code"] = False
                
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=config.embedding_config["model_name"],
                    model_kwargs=model_kwargs,
                    encode_kwargs=config.embedding_config["encode_kwargs"],
                    cache_folder="./.cache/embeddings" if config.rag_config.get("cache_embeddings", True) else None
                )

            # Инициализация текстового сплиттера (упрощенные настройки для serverless)
            chunk_size = config.text_splitter_config["chunk_size"]
            chunk_overlap = config.text_splitter_config["chunk_overlap"]
            
            if config.rag_config.get("serverless_mode", True):
                # Уменьшаем размер чанков для быстрой обработки
                chunk_size = min(chunk_size, 800)
                chunk_overlap = min(chunk_overlap, 100)
            
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )

            # Инициализация векторной БД
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    embedding_function=self.embeddings,
                    collection_name=config.rag_config["collection_name"]
                )

            logger.info("RAG components initialized successfully (serverless optimized)")

        except Exception as e:
            logger.error(f"Failed to initialize RAG components: {e}")
            raise

    def get_system_info(self) -> RAGSystemInfo:
        """Получение информации о системе для health check"""
        try:
            document_count = 0
            if self.initialization_status == "ready" and self.vectorstore:
                try:
                    # Безопасно получаем количество документов
                    if hasattr(self.vectorstore, '_collection') and self.vectorstore._collection:
                        collection = self.vectorstore._collection
                        document_count = len(collection.get()["ids"])
                    elif hasattr(self.vectorstore, 'get') and callable(self.vectorstore.get):
                        # Альтернативный способ получения количества
                        result = self.vectorstore.get()
                        document_count = len(result.get("ids", [])) if result else 0
                except Exception as e:
                    logger.warning(f"Failed to get document count: {e}")
                    document_count = 0

            # Добавляем информацию о QueryProcessor в статистику
            enhanced_stats = dict(self.stats)
            if self.query_processor:
                enhanced_stats["query_processor"] = self.query_processor.get_stats()

            return RAGSystemInfo(
                status=self.initialization_status,
                document_count=document_count,
                last_indexing_time=self.stats.get("last_indexing_time"),
                stats=enhanced_stats,
                error=self.initialization_error if self.initialization_status == "failed" else None
            )
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return RAGSystemInfo(
                status="error",
                document_count=0,
                last_indexing_time=None,
                stats=self.stats,
                error=str(e)
            )

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
        Поиск релевантных документов с ленивой инициализацией (оптимизировано для serverless)

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
            # Ленивая инициализация при первом обращении
            if not await self._ensure_initialized():
                error_msg = f"RAG system initialization failed: {self.initialization_error}"
                search_time = time.time() - start_time
                self.stats["failed_searches"] += 1

                logger.warning(f"RAG search failed for user {user_id}: {error_msg} (time: {search_time:.2f}s)")

                return {
                    "context": "",
                    "documents_found": 0,
                    "search_time": search_time,
                    "documents_info": [],
                    "similarity_scores": [],
                    "analysis_result": None,
                    "queries_used": None,
                    "error": error_msg
                }

            # БЕЗОПАСНОСТЬ: используем полный пайплайн при приоритете безопасности
            if config.rag_config.get("security_first", True):
                return await self._perform_enhanced_search(query, user_id, session_id)
            else:
                # Fallback к простому поиску только если отключена безопасность
                return await self._perform_basic_search(query, user_id, session_id)

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
                "similarity_scores": [],
                "analysis_result": None,
                "queries_used": None,
                "error": str(e)
            }

    async def _perform_enhanced_search(self, query: str, user_id: str, session_id: str) -> Dict[str, Any]:
        """Выполнение улучшенного поиска с полным анализом безопасности"""
        start_time = time.time()

        # БЕЗОПАСНОСТЬ: проверяем наличие QueryProcessor
        if not self.query_processor:
            logger.error(f"QueryProcessor not available for security analysis of query from user {user_id}")
            # Fallback к базовому поиску если QueryProcessor недоступен
            return await self._perform_basic_search(query, user_id, session_id)

        # Анализируем запрос через LLM для безопасности
        analysis_result = await self.query_processor.analyze_and_rephrase_query(query, user_id, session_id)

        # БЕЗОПАСНОСТЬ: логируем анализ запроса для аудита
        logger.info(f"RAG query analysis for user {user_id}: rag_required={analysis_result.rag_required}, "
                   f"rephrased_queries={len(analysis_result.rephrased_queries) if analysis_result.rephrased_queries else 0}")

        # Если RAG не требуется, возвращаем пустой результат
        if not analysis_result.rag_required:
            search_time = time.time() - start_time
            self.stats["successful_searches"] += 1

            return {
                "context": "",
                "documents_found": 0,
                "search_time": search_time,
                "documents_info": [],
                "similarity_scores": [],
                "analysis_result": analysis_result,
                "queries_used": [],
                "error": None
            }

        # Выполняем поиск по всем перефразированным запросам (безопасный анализ)
        all_results = []
        queries_to_search = analysis_result.rephrased_queries if analysis_result.rephrased_queries else [query]

        # БЕЗОПАСНОСТЬ: логируем все поисковые запросы для аудита
        logger.info(f"Executing enhanced RAG search for user {user_id} with {len(queries_to_search)} queries")

        for search_query in queries_to_search:
            query_results = await self._perform_basic_search(search_query, user_id, session_id)
            if query_results["context"]:  # Только если есть результаты
                all_results.append(query_results)

        # Объединяем результаты из всех запросов
        if all_results:
            combined_context = "\n\n".join([r["context"] for r in all_results])
            combined_docs_info = []
            combined_scores = []

            for result in all_results:
                combined_docs_info.extend(result["documents_info"])
                combined_scores.extend(result["similarity_scores"])

            # Убираем дубликаты документов (по filename)
            seen_files = set()
            unique_docs_info = []
            unique_scores = []

            for doc_info, score in zip(combined_docs_info, combined_scores):
                if doc_info.filename not in seen_files:
                    seen_files.add(doc_info.filename)
                    unique_docs_info.append(doc_info)
                    unique_scores.append(score)

            search_time = time.time() - start_time
            self.stats["successful_searches"] += 1

            return {
                "context": combined_context,
                "documents_found": len(unique_docs_info),
                "search_time": search_time,
                "documents_info": unique_docs_info,
                "similarity_scores": unique_scores,
                "analysis_result": analysis_result,
                "queries_used": queries_to_search,
                "error": None
            }
        else:
            # Нет результатов ни по одному запросу
            search_time = time.time() - start_time
            self.stats["successful_searches"] += 1

            return {
                "context": "",
                "documents_found": 0,
                "search_time": search_time,
                "documents_info": [],
                "similarity_scores": [],
                "analysis_result": analysis_result,
                "queries_used": queries_to_search,
                "error": None
            }

    async def _perform_basic_search(self, query: str, user_id: str, session_id: str) -> Dict[str, Any]:
        """Выполнение базового поиска с проверками безопасности"""
        start_time = time.time()

        # БЕЗОПАСНОСТЬ: логируем все поисковые запросы для аудита
        logger.info(f"Performing basic RAG search for user {user_id}, session {session_id}, query length: {len(query)}")

        # Проверяем, что vectorstore инициализирован
        if self.vectorstore is None:
            error_msg = "Vector store is not initialized"
            search_time = time.time() - start_time
            self.stats["failed_searches"] += 1

            logger.error(f"RAG search failed for user {user_id}: {error_msg} (time: {search_time:.2f}s)")

            return {
                "context": "",
                "documents_found": 0,
                "search_time": search_time,
                "documents_info": [],
                "similarity_scores": [],
                "analysis_result": None,
                "queries_used": None,
                "error": error_msg
            }

        similarity_threshold = config.rag_config["similarity_threshold"]
        min_docs = config.rag_config["min_documents"]
        max_search = config.rag_config["max_search_results"]

        # Поиск с оценками схожести
        search_k = min(max_search, config.rag_config["max_documents"] * 3)
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
        max_docs = config.rag_config["max_documents"]
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
            "similarity_scores": similarity_scores,
            "analysis_result": None,
            "queries_used": [query],
            "error": None
        }

    def _get_file_type(self, content: str) -> str:
        """Определение типа файла по содержимому"""
        if "PDF" in content[:100].upper():
            return "pdf"
        return "text"


    def reload_documents(self):
        """Перезагрузка документов"""
        logger.info("Reloading documents...")
        self.documents = []
        self._load_documents()
        logger.info("Documents reloaded")


