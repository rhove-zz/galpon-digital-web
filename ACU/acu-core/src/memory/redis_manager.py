"""
Redis manager for horizontal scalability.
Handles distributed rate limiting and session tracking.
"""

import time
import json
from typing import Any, Awaitable, Dict, Optional, List, cast
from redis.asyncio import Redis, from_url

from src.config.settings import system_config
from src.utils.logger import log


class RedisManager:
    """Manages connection to Redis and provides distributed primitives."""

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.enabled = bool(system_config.redis_url)
        self._local_pending_tools: dict = {}

    async def connect(self):
        """Initialize the Redis connection."""
        if not self.enabled:
            return

        try:
            self.redis = from_url(system_config.redis_url, decode_responses=True)
            await self.redis.ping()
            log.info(f"Conectado exitosamente a Redis: {system_config.redis_url}")
        except Exception as e:
            log.error(f"Error conectando a Redis: {e}")
            self.redis = None
            self.enabled = False

    async def disconnect(self):
        """Close the Redis connection."""
        if self.redis:
            await self.redis.aclose()
            log.info("Conexión a Redis cerrada.")

    async def is_rate_limited(self, identity: str, limit: int, window: int) -> bool:
        """
        Check if a given identity has exceeded the rate limit using a sliding window.
        Returns True if limited, False otherwise.
        """
        if not self.redis or not self.enabled:
            return False

        now = time.time()
        key = f"rate_limit:{identity}"

        try:
            # We use a Redis Pipeline to ensure atomicity
            async with self.redis.pipeline(transaction=True) as pipe:
                # Remove timestamps older than the window
                pipe.zremrangebyscore(key, 0, now - window)
                # Count the number of requests in the current window
                pipe.zcard(key)
                # Add current request timestamp
                pipe.zadd(key, {str(now): now})
                # Set expiration so we don't leak memory
                pipe.expire(key, window)

                results = await pipe.execute()

            request_count = results[1]
            return request_count >= limit

        except Exception as e:
            log.error(f"Error en Rate Limiting (Redis): {e}")
            return False

    async def record_webhook_metric(
        self,
        channel: str,
        event: str,
        error: str | None = None,
        ttl: int = 604800,
    ) -> bool:
        """Increment shared webhook metrics for multi-replica deployments."""
        if not self.redis or not self.enabled:
            return False

        key = f"webhook_metrics:{channel}"
        now = time.time()
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.hincrby(key, event, 1)
                pipe.hset(key, "last_event_at", str(now))
                if error:
                    pipe.hset(key, "last_error", error)
                pipe.expire(key, ttl)
                await pipe.execute()
            return True
        except Exception as e:
            log.error(f"Error registrando metricas webhook en Redis: {e}")
            return False

    async def get_webhook_metrics(self, channels: tuple[str, ...]) -> Optional[dict]:
        """Return shared webhook metrics from Redis when available."""
        if not self.redis or not self.enabled:
            return None

        channel_metrics = {}
        try:
            for channel in channels:
                key = f"webhook_metrics:{channel}"
                raw_metrics = await cast(Awaitable[dict], self.redis.hgetall(key))
                channel_metrics[channel] = self._normalize_webhook_metrics(raw_metrics)
            return channel_metrics
        except Exception as e:
            log.error(f"Error obteniendo metricas webhook de Redis: {e}")
            return None

    async def save_session_history(
        self, session_id: str, history: List[dict], ttl: int = 86400
    ) -> bool:
        """Saves session message history to Redis with a TTL."""
        if not self.redis or not self.enabled:
            return False

        key = f"session_history:{session_id}"
        try:
            await self.redis.set(key, json.dumps(history), ex=ttl)
            return True
        except Exception as e:
            log.error(f"Error guardando sesion en Redis: {e}")
            return False

    async def get_session_history(self, session_id: str) -> Optional[List[dict]]:
        """Retrieves session message history from Redis."""
        if not self.redis or not self.enabled:
            return None

        key = f"session_history:{session_id}"
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            log.error(f"Error obteniendo sesion de Redis: {e}")
            return None

    @staticmethod
    def _normalize_webhook_metrics(raw_metrics: dict) -> Dict[str, Any]:
        """Normalize Redis hash values into webhook metric primitives."""
        normalized: Dict[str, Any] = {
            "received": 0,
            "accepted": 0,
            "rejected": 0,
            "ignored": 0,
            "processed": 0,
            "failed": 0,
            "last_event_at": None,
            "last_error": None,
        }
        for counter in (
            "received",
            "accepted",
            "rejected",
            "ignored",
            "processed",
            "failed",
        ):
            try:
                normalized[counter] = int(raw_metrics.get(counter, 0) or 0)
            except (TypeError, ValueError):
                normalized[counter] = 0
        last_event_at = raw_metrics.get("last_event_at")
        if last_event_at not in (None, ""):
            try:
                normalized["last_event_at"] = float(str(last_event_at))
            except (TypeError, ValueError):
                normalized["last_event_at"] = None
        normalized["last_error"] = raw_metrics.get("last_error") or None
        return normalized

    async def set_shared_memory(
        self, session_id: str, key: str, value: str, ttl: int = 86400
    ) -> bool:
        """Saves a value in the shared stateful workflow memory."""
        if not self.redis or not self.enabled:
            return False

        redis_key = f"shared_memory:{session_id}"
        try:
            await cast(Awaitable[Any], self.redis.hset(redis_key, key, value))
            await self.redis.expire(redis_key, ttl)
            return True
        except Exception as e:
            log.error(f"Error guardando memoria compartida en Redis: {e}")
            return False

    async def get_shared_memory(self, session_id: str, key: str) -> Optional[str]:
        """Retrieves a value from the shared stateful workflow memory."""
        if not self.redis or not self.enabled:
            return None

        redis_key = f"shared_memory:{session_id}"
        try:
            data = await cast(Awaitable[Any], self.redis.hget(redis_key, key))
            return str(data) if data is not None else None
        except Exception as e:
            log.error(f"Error obteniendo memoria compartida de Redis: {e}")
            return None

    async def set_pending_tool(
        self, tool_id: str, tool_data: dict, ttl: int = 3600
    ) -> bool:
        """Store a pending tool call awaiting authorization."""
        if not self.redis or not self.enabled:
            self._local_pending_tools[tool_id] = {
                **tool_data,
                "expires": time.time() + ttl,
            }
            return True

        key = f"pending_tool:{tool_id}"
        try:
            await self.redis.set(key, json.dumps(tool_data), ex=ttl)
            return True
        except Exception as e:
            log.error(f"Error setting pending tool: {e}")
            return False

    async def get_pending_tool(self, tool_id: str) -> Optional[dict]:
        """Get the current state of a pending tool call."""
        if not self.redis or not self.enabled:
            data = self._local_pending_tools.get(tool_id)
            if data and data["expires"] > time.time():
                return {k: v for k, v in data.items() if k != "expires"}
            elif data:
                del self._local_pending_tools[tool_id]
            return None

        key = f"pending_tool:{tool_id}"
        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    async def resolve_pending_tool(self, tool_id: str, status: str) -> bool:
        """Update the status of a pending tool call (approved/rejected)."""
        data = await self.get_pending_tool(tool_id)
        if not data:
            return False

        data["status"] = status

        if not self.redis or not self.enabled:
            self._local_pending_tools[tool_id].update(data)
            return True

        key = f"pending_tool:{tool_id}"
        try:
            await self.redis.set(key, json.dumps(data), keepttl=True)
            return True
        except Exception:
            return False

    async def get_all_pending_tools(self) -> List[dict]:
        """Retrieve all currently pending tools for the dashboard."""
        tools = []
        if not self.redis or not self.enabled:
            now = time.time()
            for k, v in list(self._local_pending_tools.items()):
                if v["expires"] > now:
                    tools.append(
                        {
                            **{key: val for key, val in v.items() if key != "expires"},
                            "id": k,
                        }
                    )
                else:
                    del self._local_pending_tools[k]
            return tools

        try:
            keys = await self.redis.keys("pending_tool:*")
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    parsed = json.loads(data)
                    parsed["id"] = key.replace("pending_tool:", "")
                    tools.append(parsed)
            return tools
        except Exception:
            return tools


# Global instance
redis_manager = RedisManager()
