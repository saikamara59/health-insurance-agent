import json
from abc import ABC, abstractmethod


class SessionStore(ABC):
    @abstractmethod
    def save(self, session_id: str, data: dict) -> None: ...

    @abstractmethod
    def load(self, session_id: str) -> dict | None: ...


class InMemoryStore(SessionStore):
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def save(self, session_id: str, data: dict) -> None:
        self._store[session_id] = data

    def load(self, session_id: str) -> dict | None:
        return self._store.get(session_id)


class RedisStore(SessionStore):
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        import redis

        self._client = redis.from_url(redis_url)
        self._ttl = 3600

    def save(self, session_id: str, data: dict) -> None:
        self._client.setex(session_id, self._ttl, json.dumps(data))

    def load(self, session_id: str) -> dict | None:
        raw = self._client.get(session_id)
        if raw is None:
            return None
        return json.loads(raw)
