from langchain.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List
import os
from loguru import logger

class RAGSystem:
    def __init__(self, persist_directory: str = "./chroma_db", data_directory: str = "./data"):
        # Инициализация локальных эмбеддингов
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},  # Используйте 'cuda' для GPU
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Инициализация текстового сплиттера
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # Загрузка документов из указанной директории
        self.load_documents(data_directory)
        
        # Инициализация векторной базы данных
        self.vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embeddings
        )

    def load_documents(self, data_directory: str):
        """Загрузка всех текстовых файлов из указанной директории"""
        try:
            loader = DirectoryLoader(
                data_directory,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            self.documents = loader.load()
            logger.info(f"Loaded {len(self.documents)} documents from {data_directory}")
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
            self.documents = []

    async def add_documents(self):
        """Добавление документов в векторную базу данных"""
        if not self.documents:
            logger.warning("No documents to add")
            return

        # Разделение документов на чанки
        split_docs = self.text_splitter.split_documents(self.documents)
        
        # Добавление в векторную базу
        self.vectorstore.add_documents(
            documents=split_docs,
            embedding=self.embeddings
        )
        logger.info(f"Added {len(split_docs)} document chunks to vector store")

    async def search_relevant_docs(self, query: str, k: int = 4) -> List[str]:
        """Поиск релевантных документов"""
        results = self.vectorstore.similarity_search(
            query=query,
            k=k
        )
        return [doc.page_content for doc in results]

    def delete_collection(self):
        """Удаление коллекции"""
        try:
            self.vectorstore.delete_collection()
            logger.info("Collection deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")

# Пример использования
async def main():
    rag = RAGSystem(
        persist_directory="./chroma_db",
        data_directory="./data"  # Папка с вашими текстовыми файлами
    )
    
    await rag.add_documents()
    results = await rag.search_relevant_docs("Ваш запрос")
    print(results)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())