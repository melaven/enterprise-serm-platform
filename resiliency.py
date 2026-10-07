import asyncio
import logging
import random
import time
from typing import Callable, Any, Dict
from fastapi import HTTPException
from supabase import create_client, Client

logger = logging.getLogger("tenable_nexus.resiliency")

class TenableRetryHandler:
    def __init__(self, supabase_url: str, supabase_key: str):
        # Официальный клиент supabase-py
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.max_retries = 3
        self.base_delay = 2.0

    async def execute_with_retry(self, api_call_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Выполняет любой асинхронный запрос бэкенда Tenable Nexus с экспоненциальным бэкаффом и джиттером.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(api_call_func):
                    return await api_call_func(*args, **kwargs)
                else:
                    return api_call_func(*args, **kwargs)
                    
            except Exception as e:
                error_str = str(e)
                logger.warning(f"[Попытка {attempt}/{self.max_retries}] Сбой функции {api_call_func.__name__}. Ошибка: {error_str}")
                
                if attempt == self.max_retries:
                    # Если все 3 попытки сгорели, пишем лог в Supabase сайта и отдаем 502
                    await self._log_error_to_supabase(error_str, api_call_func.__name__, kwargs)
                    raise HTTPException(
                        status_code=502, 
                        detail="Внешний ИИ/CRM сервис Tenable Nexus недоступен после 3 попыток запроса."
                    )
                
                # Экспоненциальный бэкафф + случайный джиттер до 1 секунды
                delay = (self.base_delay ** attempt) + random.uniform(0.0, 1.0)
                await asyncio.sleep(delay)

    async def _log_error_to_supabase(self, error_message: str, function_name: str, payload: Dict[str, Any]) -> None:
        """Записывает критический сбой инфраструктуры в таблицу логирования Supabase."""
        try:
            log_data = {
                "system_core": "Tenable_Nexus_Backend",
                "failed_function": function_name,
                "error_payload": error_message,
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "context_metadata": str(payload)
            }
            self.supabase.table("system_logs").insert(log_data).execute()
            logger.info("Лог сбоя Tenable Nexus успешно отправлен в Supabase.")
        except Exception as sb_err:
            logger.error(f"Сбой логирования Supabase: {str(sb_err)}")
            