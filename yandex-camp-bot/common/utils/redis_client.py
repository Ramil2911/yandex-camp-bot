import json
import redis
from typing import Dict, Any, Optional, List
from loguru import logger
from ..config import config


class RedisClient:
    """Клиент для работы с Redis"""
    
    def __init__(self):
        self.redis_client = None
        self.connection_status = "disconnected"
        
        try:
            self.redis_client = redis.from_url(
                config.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Тестируем подключение
            self.redis_client.ping()
            self.connection_status = "connected"
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.connection_status = "disconnected"
            self.redis_client = None

    def is_connected(self) -> bool:
        """Проверка подключения к Redis"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    async def set_dialogue(self, session_id: str, dialogue_data: Dict[str, Any], ttl: int = 86400) -> bool:
        """Сохранение диалога в Redis"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return False
        
        try:
            key = f"dialogue:{session_id}"
            self.redis_client.setex(key, ttl, json.dumps(dialogue_data))
            logger.debug(f"Dialogue saved for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save dialogue for session {session_id}: {e}")
            return False

    async def get_dialogue(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получение диалога из Redis"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return None
        
        try:
            key = f"dialogue:{session_id}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get dialogue for session {session_id}: {e}")
            return None

    async def add_message(self, session_id: str, message: Dict[str, Any], ttl: int = 86400) -> bool:
        """Добавление сообщения к диалогу"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return False
        
        try:
            # Получаем текущий диалог
            dialogue = await self.get_dialogue(session_id)
            if not dialogue:
                # Создаем новый диалог
                dialogue = {
                    "session_id": session_id,
                    "user_id": message.get("user_id", "unknown"),
                    "created_at": message.get("timestamp"),
                    "last_activity": message.get("timestamp"),
                    "messages": [],
                    "message_count": 0,
                    "metadata": {}
                }
            
            # Добавляем сообщение
            dialogue["messages"].append(message)
            dialogue["message_count"] = len(dialogue["messages"])
            dialogue["last_activity"] = message.get("timestamp")
            
            # Ограничиваем количество сообщений (например, последние 100)
            max_messages = 100
            if len(dialogue["messages"]) > max_messages:
                dialogue["messages"] = dialogue["messages"][-max_messages:]
            
            # Сохраняем обновленный диалог
            return await self.set_dialogue(session_id, dialogue, ttl)
            
        except Exception as e:
            logger.error(f"Failed to add message to dialogue {session_id}: {e}")
            return False

    async def clear_dialogue(self, session_id: str) -> bool:
        """Очистка диалога"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return False
        
        try:
            key = f"dialogue:{session_id}"
            result = self.redis_client.delete(key)
            logger.info(f"Dialogue cleared for session {session_id}")
            return result > 0
        except Exception as e:
            logger.error(f"Failed to clear dialogue for session {session_id}: {e}")
            return False

    async def get_dialogue_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение истории диалога"""
        dialogue = await self.get_dialogue(session_id)
        if not dialogue:
            return []
        
        messages = dialogue.get("messages", [])
        return messages[-limit:] if limit > 0 else messages

    async def get_dialogue_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получение статистики диалога"""
        dialogue = await self.get_dialogue(session_id)
        if not dialogue:
            return None
        
        return {
            "session_id": session_id,
            "user_id": dialogue.get("user_id"),
            "message_count": dialogue.get("message_count", 0),
            "created_at": dialogue.get("created_at"),
            "last_activity": dialogue.get("last_activity"),
            "is_active": True
        }

    async def search_dialogues_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Поиск диалогов по trace_id"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return []
        
        try:
            # Получаем все ключи диалогов
            pattern = "dialogue:*"
            keys = self.redis_client.keys(pattern)
            
            matching_dialogues = []
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        dialogue = json.loads(data)
                        # Ищем trace_id в сообщениях
                        for message in dialogue.get("messages", []):
                            if message.get("trace_id") == trace_id:
                                matching_dialogues.append({
                                    "session_id": dialogue.get("session_id"),
                                    "user_id": dialogue.get("user_id"),
                                    "message": message,
                                    "dialogue_stats": {
                                        "message_count": dialogue.get("message_count", 0),
                                        "created_at": dialogue.get("created_at"),
                                        "last_activity": dialogue.get("last_activity")
                                    }
                                })
                                break
                except Exception as e:
                    logger.warning(f"Failed to process dialogue key {key}: {e}")
                    continue
            
            return matching_dialogues
            
        except Exception as e:
            logger.error(f"Failed to search dialogues by trace {trace_id}: {e}")
            return []

    async def get_all_active_dialogues(self) -> List[Dict[str, Any]]:
        """Получение всех активных диалогов"""
        if not self.is_connected():
            logger.error("Redis not connected")
            return []
        
        try:
            pattern = "dialogue:*"
            keys = self.redis_client.keys(pattern)
            
            dialogues = []
            for key in keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        dialogue = json.loads(data)
                        dialogues.append({
                            "session_id": dialogue.get("session_id"),
                            "user_id": dialogue.get("user_id"),
                            "message_count": dialogue.get("message_count", 0),
                            "created_at": dialogue.get("created_at"),
                            "last_activity": dialogue.get("last_activity")
                        })
                except Exception as e:
                    logger.warning(f"Failed to process dialogue key {key}: {e}")
                    continue
            
            return dialogues
            
        except Exception as e:
            logger.error(f"Failed to get all active dialogues: {e}")
            return []

    async def close(self):
        """Закрытие соединения с Redis"""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Failed to close Redis connection: {e}")


# Глобальный экземпляр клиента
redis_client = RedisClient()
