"""
API Gateway клиент - теперь использует общий ServiceHTTPClient из common.utils.http_client
"""

# Импортируем общий клиент вместо локального
from common.utils.http_client import service_http_client as service_client
