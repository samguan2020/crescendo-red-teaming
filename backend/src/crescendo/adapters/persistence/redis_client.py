"""
Minimal async Redis client abstraction for the job-state projection.

LocalRedisClient wraps redis.asyncio; InMemoryRedisClient is an opt-in dev
fallback (single process only). Only the operations the projection needs are
exposed.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class BaseRedisClient(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    async def get_json(self, key: str) -> dict | None:
        data = await self.get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value: dict, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(value), ttl)


class LocalRedisClient(BaseRedisClient):
    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None

    async def connect(self) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(self._url, decode_responses=True)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl:
            await self._client.setex(key, ttl, value)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)


class InMemoryRedisClient(BaseRedisClient):
    """Process-local dict. Dev only - state is lost on restart / not shared."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        self._store.clear()

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
