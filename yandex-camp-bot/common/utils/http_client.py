import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, Union
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class ServiceHTTPClient:
    """HTTP клиент для межсервисного взаимодействия"""

    def __init__(self, timeout: float = 30.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self._client: Optional[httpx.AsyncClient] = None

    @asynccontextmanager
    async def _get_client(self):
        """Получение HTTP клиента"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)

        try:
            yield self._client
        except Exception as e:
            logger.error(f"HTTP client error: {str(e)}")
            raise
        finally:
            pass

    async def close(self):
        """Закрытие HTTP клиента"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: Optional[int] = None
    ) -> httpx.Response:
        """Выполнение HTTP запроса с повторными попытками"""

        retry_count = retries or self.retries

        for attempt in range(retry_count + 1):
            try:
                async with self._get_client() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        data=data,
                        json=json,
                        headers=headers
                    )

                    # Не повторять для клиентских ошибок
                    if response.status_code < 500:
                        return response

                    if attempt < retry_count:
                        wait_time = 2 ** attempt  # Экспоненциальная задержка
                        logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < retry_count:
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection error (attempt {attempt + 1}): {str(e)}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Final attempt failed: {str(e)}")
                    raise

        raise Exception(f"HTTP request failed after {retry_count + 1} attempts")

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """GET запрос"""
        return await self.request("GET", url, headers=headers)

    async def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """POST запрос"""
        return await self.request("POST", url, data=data, json=json, headers=headers)

    async def put(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """PUT запрос"""
        return await self.request("PUT", url, data=data, json=json, headers=headers)

    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """DELETE запрос"""
        return await self.request("DELETE", url, headers=headers)


# Глобальный экземпляр клиента
service_http_client = ServiceHTTPClient()


async def health_check_service(service_url: str, service_name: str) -> Dict[str, Any]:
    """Проверка здоровья сервиса"""
    try:
        response = await service_http_client.get(f"{service_url}/health")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Health check failed for {service_name}: {str(e)}")
        return {
            "status": "unhealthy",
            "service": service_name,
            "error": str(e)
        }
