import time
from typing import Protocol


class ProviderCache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, data: dict) -> None: ...


class InMemoryProviderCache:
    def __init__(self, ttl_seconds: int = 86400) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None
        return entry["data"]

    def set(self, key: str, data: dict) -> None:
        self._store[key] = {
            "data": data,
            "expires_at": time.time() + self.ttl_seconds,
        }


class RedisProviderCache:
    def __init__(self, redis_client: object, ttl_seconds: int = 86400) -> None:
        self.ttl_seconds = ttl_seconds
        self._redis = redis_client

    def get(self, key: str) -> dict | None:
        import json

        raw = self._redis.get(key)  # type: ignore[union-attr]
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, data: dict) -> None:
        import json

        self._redis.setex(key, self.ttl_seconds, json.dumps(data))  # type: ignore[union-attr]
