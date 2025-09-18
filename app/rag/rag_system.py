"""
Базовая RAG система для загрузки документов и поиска релевантной информации.
"""

import warnings
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Optional
import os
from loguru import logger

# Подавляем предупреждения о deprecated классах
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community.embeddings")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_community.vectorstores")

from .rag_config import EMBEDDING_CONFIG, TEXT_SPLITTER_CONFIG, VECTORSTORE_CONFIG


class RAGSystem:
    """Базовая RAG система для работы с документами и векторным поиском"""
    
    def __init__(self, 
                 persist_directory: str = "./chroma_db", 
                 data_directory: str = "./data"):
        """
        Инициализация RAG системы
        
        Args:
            persist_directory: Директория для хранения векторной БД
            data_directory: Директория с документами
        """
        self.persist_directory = persist_directory
        self.data_directory = data_directory
        self.documents = []
        
        # Инициализация компонентов
        self._init_embeddings()
        self._init_text_splitter()
        self._init_vectorstore()
        
        # Загрузка документов
        self.load_documents(data_directory)
    
    def _init_embeddings(self):
        """Инициализация эмбеддингов"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_CONFIG["model_name"],
                model_kwargs=EMBEDDING_CONFIG["model_kwargs"],
                encode_kwargs=EMBEDDING_CONFIG["encode_kwargs"]
            )
        logger.debug("Эмбеддинги инициализированы")
    
    def _init_text_splitter(self):
        """Инициализация текстового сплиттера"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=TEXT_SPLITTER_CONFIG["chunk_size"],
            chunk_overlap=TEXT_SPLITTER_CONFIG["chunk_overlap"],
            length_function=TEXT_SPLITTER_CONFIG["length_function"],
            separators=TEXT_SPLITTER_CONFIG["separators"]
        )
        logger.debug("Текстовый сплиттер инициализирован")
    
    def _init_vectorstore(self):
        """Инициализация векторной БД"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        logger.debug("Векторная БД инициализирована")
    
    def load_documents(self, data_directory: str):
        """Загрузка всех текстовых и PDF файлов из указанной директории"""
        try:
            if not os.path.exists(data_directory):
                logger.warning(f"Директория {data_directory} не существует")
                self.documents = []
                return
            
            self.documents = []
            
            # Загрузка TXT файлов
            txt_loader = DirectoryLoader(
                data_directory,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            txt_docs = txt_loader.load()
            self.documents.extend(txt_docs)
            logger.info(f"Загружено {len(txt_docs)} TXT документов")
            
            # Загрузка PDF файлов
            pdf_loader = DirectoryLoader(
                data_directory,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader
            )
            pdf_docs = pdf_loader.load()
            self.documents.extend(pdf_docs)
            logger.info(f"Загружено {len(pdf_docs)} PDF документов")
            
            logger.info(f"Всего загружено {len(self.documents)} документов из {data_directory}")
        except Exception as e:
            logger.error(f"Ошибка загрузки документов: {e}")
            self.documents = []
    
    async def add_documents(self):
        """Добавление документов в векторную базу данных"""
        if not self.documents:
            logger.warning("Нет документов для добавления")
            return
        
        try:
            # Разделение документов на чанки
            split_docs = self.text_splitter.split_documents(self.documents)
            
            # Добавление в векторную базу
            self.vectorstore.add_documents(
                documents=split_docs,
                embedding=self.embeddings
            )
            logger.info(f"Добавлено {len(split_docs)} чанков документов в векторную БД")
        except Exception as e:
            logger.error(f"Ошибка добавления документов в векторную БД: {e}")
            raise
    
    async def search_relevant_docs(self, query: str, k: int = 4, similarity_threshold: float = None) -> List[str]:
        """
        Поиск релевантных документов с пороговой фильтрацией
        
        Args:
            query: Поисковый запрос
            k: Количество документов для возврата
            similarity_threshold: Порог схожести (0.0-1.0), None для использования из конфигурации
            
        Returns:
            List[str]: Список релевантных документов, отфильтрованных по порогу
        """
        try:
            from .rag_config import RAG_CONFIG
            
            # Используем параметры из конфигурации
            if similarity_threshold is None:
                similarity_threshold = RAG_CONFIG.get("similarity_threshold", 0.7)
            
            min_docs = RAG_CONFIG.get("min_documents", 1)
            max_search = RAG_CONFIG.get("max_search_results", 10)
            
            # Поиск с оценками схожести (ищем больше, чем нужно, для лучшей фильтрации)
            search_k = min(max_search, k * 3)  # Ищем в 3 раза больше для лучшей фильтрации
            results_with_scores = self.vectorstore.similarity_search_with_score(
                query=query,
                k=search_k
            )
            
            # Фильтрация по порогу схожести
            filtered_results = []
            for doc, score in results_with_scores:
                # Для ChromaDB score - это расстояние (чем меньше, тем лучше)
                # Конвертируем в схожесть: similarity = 1 / (1 + distance)
                # Это дает значения от 0 до 1, где 1 = идеальное совпадение
                similarity = 1 / (1 + score)
                
                if similarity >= similarity_threshold:
                    filtered_results.append(doc.page_content)
                    logger.debug(f"Документ принят: similarity={similarity:.3f}, threshold={similarity_threshold:.3f}")
                else:
                    logger.debug(f"Документ отсечен: similarity={similarity:.3f}, threshold={similarity_threshold:.3f}")
            
            # Ограничиваем количество результатов
            filtered_results = filtered_results[:k]
            
            # Если результатов меньше минимального, возвращаем лучшие из найденных
            if len(filtered_results) < min_docs and results_with_scores:
                logger.warning(f"Найдено только {len(filtered_results)} документов выше порога {similarity_threshold:.3f}, возвращаем лучшие {min_docs}")
                # Берем лучшие результаты независимо от порога
                best_results = []
                for doc, score in results_with_scores[:min_docs]:
                    best_results.append(doc.page_content)
                filtered_results = best_results
            
            logger.info(f"Найдено {len(filtered_results)} релевантных документов из {len(results_with_scores)} (порог: {similarity_threshold:.3f})")
            return filtered_results
            
        except Exception as e:
            logger.error(f"Ошибка поиска документов: {e}")
            return []
    
    def get_document_count(self) -> int:
        """Получение количества загруженных документов"""
        return len(self.documents)
    
    def get_vectorstore_info(self) -> dict:
        """Получение информации о векторной БД"""
        try:
            collection = self.vectorstore._collection
            return {
                "collection_name": collection.name,
                "document_count": collection.count(),
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о векторной БД: {e}")
            return {}
    
    def delete_collection(self):
        """Удаление коллекции"""
        try:
            self.vectorstore.delete_collection()
            logger.info("Коллекция успешно удалена")
        except Exception as e:
            logger.error(f"Ошибка удаления коллекции: {e}")
    
    def reload_documents(self):
        """Перезагрузка документов"""
        logger.info("Перезагрузка документов...")
        self.load_documents(self.data_directory)
        logger.info("Документы перезагружены")
