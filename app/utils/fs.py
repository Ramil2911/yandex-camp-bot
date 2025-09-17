import boto3
import os
import tempfile
from typing import List, Optional

from app.utils.log import logger, log_user_action, log_security_event, log_api_call, log_metrics, log_system_event
from langchain_core.documents import Document


class S3Client:
    """Класс для работы с Yandex Object Storage (S3)"""

    def __init__(self):
        """Инициализация S3 клиента с параметрами из переменных окружения"""
        self.endpoint_url = os.getenv('YC_S3_ENDPOINT')
        self.access_key = os.getenv('YC_S3_ACCESS_KEY')
        self.secret_key = os.getenv('YC_S3_SECRET_KEY')
        self.bucket = os.getenv('YC_S3_BUCKET')
        self.prefix = os.getenv('YC_S3_PREFIX', '')

        # Проверяем обязательные параметры
        if not all([self.endpoint_url, self.access_key, self.secret_key, self.bucket]):
            missing = []
            if not self.endpoint_url: missing.append('YC_S3_ENDPOINT')
            if not self.access_key: missing.append('YC_S3_ACCESS_KEY')
            if not self.secret_key: missing.append('YC_S3_SECRET_KEY')
            if not self.bucket: missing.append('YC_S3_BUCKET')

            error_msg = f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
            log_system_event("s3_config_error", error_msg, "ERROR")
            raise ValueError(error_msg)

        # Создаем S3 клиент
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name='ru-central1'
            )
            log_system_event("s3_client_initialized", f"Подключено к бакету {self.bucket}")
        except Exception as e:
            log_system_event("s3_client_init_failed", f"Ошибка инициализации S3 клиента: {str(e)}", "ERROR")
            raise

    def download_from_s3(self) -> Optional[List[Document]]:
        """
        Скачивание файлов из S3 с проверками и валидацией

        Returns:
            List[Document]: Список документов или None при ошибке
        """
        log_system_event("s3_download_started", f"Начинаем скачивание из {self.bucket}/{self.prefix}")

        try:
            # Получаем список объектов
            objects = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)

            if 'Contents' not in objects:
                log_system_event("s3_no_objects", f"В бакете {self.bucket} нет объектов с префиксом {self.prefix}")
                return self.load_and_index_documents([])

            log_system_event("s3_objects_found", f"Найдено {len(objects['Contents'])} объектов")

            local_files = []
            with tempfile.TemporaryDirectory() as tmpdir:
                log_system_event("temp_dir_created", f"Создана временная директория: {tmpdir}")

                for obj in objects['Contents']:
                    key = obj.get('Key')

                    # Проверяем key
                    if not key or not isinstance(key, str):
                        log_system_event("s3_invalid_key", f"Неверный ключ: {key}", "WARNING")
                        continue

                    # Пропускаем папки
                    if key.endswith('/'):
                        log_system_event("s3_skipping_directory", f"Пропускаем директорию: {key}")
                        continue

                    # Проверяем размер файла
                    size = obj.get('Size', 0)
                    if size == 0:
                        log_system_event("s3_empty_file", f"Пустой файл: {key}")
                        continue

                    local_path = os.path.join(tmpdir, os.path.basename(key))

                    try:
                        # Скачиваем файл
                        self.s3_client.download_file(self.bucket, key, local_path)

                        # Проверяем размер после скачивания
                        downloaded_size = os.path.getsize(local_path)
                        if downloaded_size == 0:
                            log_system_event("s3_download_empty", f"Скачанный файл пустой: {key}", "WARNING")
                            continue

                        if downloaded_size != size:
                            log_system_event(
                                "s3_size_mismatch",
                                f"Размер файла не совпадает. Ожидалось: {size}, получено: {downloaded_size} для {key}",
                                "WARNING"
                            )

                        local_files.append(local_path)
                        log_system_event("s3_file_downloaded", f"Скачан файл: {key} ({downloaded_size} байт)")

                    except Exception as e:
                        log_system_event("s3_download_error", f"Ошибка скачивания {key}: {str(e)}", "ERROR")
                        continue

                log_system_event("s3_download_completed", f"Скачано {len(local_files)} файлов")
                return self.load_and_index_documents(local_files)

        except Exception as e:
            log_system_event("s3_download_failed", f"Ошибка при работе с S3: {str(e)}", "ERROR")
            return None

    def load_and_index_documents(self, local_files: List[str]) -> List[Document]:
        """
        Загрузка и индексация документов с валидацией

        Args:
            local_files: Список путей к локальным файлам

        Returns:
            List[Document]: Список валидных документов
        """
        log_system_event("document_loading_started", f"Начинаем загрузку {len(local_files)} файлов")

        docs = []

        for file_path in local_files:
            try:
                # Читаем содержимое файла
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Валидируем содержимое
                if not self._validate_document_content(content):
                    log_system_event("document_validation_failed", f"Валидация не пройдена для {file_path}", "WARNING")
                    continue

                # Создаем документ
                filename = os.path.basename(file_path)
                doc = Document(
                    page_content=content,
                    metadata={
                        'source': file_path,
                        'filename': filename,
                        'file_size': len(content)
                    }
                )

                docs.append(doc)
                log_system_event("document_loaded", f"Загружен документ: {filename}")

            except Exception as e:
                log_system_event("document_loading_error", f"Ошибка загрузки {file_path}: {str(e)}", "ERROR")
                continue

        # Если ни один документ не прошёл валидацию — создаём заглушку
        if not docs:
            log_system_event("no_valid_documents", "Ни один документ не прошёл валидацию, создаём заглушку", "WARNING")
            docs = [Document(page_content="Нет доступных документов.", metadata={})]

        log_system_event("document_loading_completed", f"Загружено {len(docs)} документов")
        return docs

    def _validate_document_content(self, content: str) -> bool:
        """
        Валидация содержимого документа

        Args:
            content: Содержимое документа

        Returns:
            bool: True если содержимое валидно
        """
        # Проверяем, что content не None
        if content is None:
            return False

        # Проверяем, что content является строкой
        if not isinstance(content, str):
            return False

        # Проверяем, что content не пустой
        if not content.strip():
            return False

        return True


class S3ClientSingleton:
    """Синглтон-обёртка для S3Client"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    def get_client(self) -> S3Client:
        """Получение экземпляра S3 клиента (ленивая инициализация)"""
        if self._client is None:
            try:
                self._client = S3Client()
            except Exception:
                # Если инициализация не удалась, не кэшируем ошибку
                raise
        return self._client

    def reset_client(self):
        """Сброс клиента (для тестирования или при изменении конфигурации)"""
        self._client = None


# Глобальный синглтон
_s3_singleton = S3ClientSingleton()

def get_s3_client() -> S3Client:
    """Получение экземпляра S3 клиента через синглтон"""
    return _s3_singleton.get_client()

def download_from_s3() -> Optional[List[Document]]:
    """Удобная функция для скачивания документов из S3"""
    client = get_s3_client()
    return client.download_from_s3()