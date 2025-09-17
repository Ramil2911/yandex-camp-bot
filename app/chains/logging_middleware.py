"""
Middleware для логирования и трейсинга LangChain пайплайна.
Автоматически логирует выполнение цепочек и собирает метрики.
"""

import time
from typing import Dict, Any, Optional, Iterator
from functools import wraps
from langchain_core.runnables import Runnable
from langchain_core.runnables.utils import Input, Output

from app.utils.log import logger, log_system_event, log_error


class LoggingRunnable(Runnable):
    """
    Wrapper для Runnable с автоматическим логированием
    """
    
    def __init__(self, runnable: Runnable, name: str = "unknown"):
        """
        Инициализация логирующего wrapper'а
        
        Args:
            runnable: Оборачиваемый Runnable
            name: Имя для логирования
        """
        self.runnable = runnable
        self.name = name
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time": 0.0
        }
    
    def invoke(self, input: Input, config: Optional[dict] = None) -> Output:
        """Синхронное выполнение с логированием"""
        start_time = time.time()
        self.stats["total_calls"] += 1
        
        try:
            result = self.runnable.invoke(input, config)
            
            duration = time.time() - start_time
            self.stats["successful_calls"] += 1
            self.stats["total_time"] += duration
            
            # Логируем только если есть проблемы или долгое выполнение
            if duration > 5.0:  # Более 5 секунд
                log_system_event(
                    f"slow_execution_{self.name}", 
                    f"Duration: {duration:.2f}s", 
                    "WARNING"
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.stats["failed_calls"] += 1
            
            log_error(
                "system", 
                "system", 
                f"Runnable {self.name} failed after {duration:.2f}s: {str(e)}"
            )
            raise
    
    async def ainvoke(self, input: Input, config: Optional[dict] = None) -> Output:
        """Асинхронное выполнение с логированием"""
        start_time = time.time()
        self.stats["total_calls"] += 1
        
        try:
            result = await self.runnable.ainvoke(input, config)
            
            duration = time.time() - start_time
            self.stats["successful_calls"] += 1
            self.stats["total_time"] += duration
            
            # Логируем только если есть проблемы или долгое выполнение
            if duration > 5.0:  # Более 5 секунд
                log_system_event(
                    f"slow_execution_{self.name}", 
                    f"Duration: {duration:.2f}s", 
                    "WARNING"
                )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.stats["failed_calls"] += 1
            
            log_error(
                "system", 
                "system", 
                f"Runnable {self.name} failed after {duration:.2f}s: {str(e)}"
            )
            raise
    
    def stream(self, input: Input, config: Optional[dict] = None) -> Iterator[Output]:
        """Потоковое выполнение с логированием"""
        start_time = time.time()
        self.stats["total_calls"] += 1
        
        try:
            for chunk in self.runnable.stream(input, config):
                yield chunk
            
            duration = time.time() - start_time
            self.stats["successful_calls"] += 1
            self.stats["total_time"] += duration
            
        except Exception as e:
            duration = time.time() - start_time
            self.stats["failed_calls"] += 1
            
            log_error(
                "system", 
                "system", 
                f"Runnable {self.name} stream failed after {duration:.2f}s: {str(e)}"
            )
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики выполнения"""
        avg_time = (
            self.stats["total_time"] / self.stats["total_calls"]
            if self.stats["total_calls"] > 0 else 0
        )
        
        success_rate = (
            self.stats["successful_calls"] / self.stats["total_calls"]
            if self.stats["total_calls"] > 0 else 0
        )
        
        return {
            **self.stats,
            "average_time": avg_time,
            "success_rate": success_rate,
            "name": self.name
        }


def with_logging(name: str):
    """
    Декоратор для добавления логирования к Runnable
    
    Args:
        name: Имя для логирования
        
    Returns:
        Декоратор
    """
    def decorator(runnable: Runnable) -> LoggingRunnable:
        return LoggingRunnable(runnable, name)
    return decorator


def create_logging_pipeline(base_pipeline: Runnable, name: str = "main_pipeline") -> LoggingRunnable:
    """
    Создание пайплайна с логированием
    
    Args:
        base_pipeline: Базовый пайплайн
        name: Имя для логирования
        
    Returns:
        LoggingRunnable: Пайплайн с логированием
    """
    return LoggingRunnable(base_pipeline, name)


class PipelineMetrics:
    """
    Сборщик метрик для всех компонентов пайплайна
    """
    
    def __init__(self):
        self.components: Dict[str, LoggingRunnable] = {}
    
    def register_component(self, name: str, component: LoggingRunnable):
        """Регистрация компонента для сбора метрик"""
        self.components[name] = component
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Получение статистики всех компонентов"""
        stats = {}
        total_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time": 0.0
        }
        
        for name, component in self.components.items():
            component_stats = component.get_stats()
            stats[name] = component_stats
            
            # Суммируем общую статистику
            total_stats["total_calls"] += component_stats["total_calls"]
            total_stats["successful_calls"] += component_stats["successful_calls"]
            total_stats["failed_calls"] += component_stats["failed_calls"]
            total_stats["total_time"] += component_stats["total_time"]
        
        # Вычисляем общие метрики
        total_stats["average_time"] = (
            total_stats["total_time"] / total_stats["total_calls"]
            if total_stats["total_calls"] > 0 else 0
        )
        total_stats["success_rate"] = (
            total_stats["successful_calls"] / total_stats["total_calls"]
            if total_stats["total_calls"] > 0 else 0
        )
        
        return {
            "components": stats,
            "total": total_stats
        }
    
    def log_summary(self):
        """Логирование общей сводки метрик"""
        stats = self.get_all_stats()
        total = stats["total"]
        
        if total["total_calls"] > 0:
            log_system_event(
                "pipeline_metrics_summary",
                f"Calls: {total['total_calls']}, "
                f"Success Rate: {total['success_rate']:.1%}, "
                f"Avg Time: {total['average_time']:.2f}s",
                "INFO"
            )


# Глобальный экземпляр для сбора метрик
pipeline_metrics = PipelineMetrics()
