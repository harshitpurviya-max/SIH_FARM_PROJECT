import asyncio
import json
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis


QUEUE_CHANNEL = "sihfarm:queue"


class ConnectionManager:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self.redis: Redis | None = None
        self.connections: set[WebSocket] = set()
        self.subscriber_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        try:
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            self.subscriber_task = asyncio.create_task(self._subscribe())
        except Exception:
            await self._close_redis()

    async def stop(self) -> None:
        if self.subscriber_task is not None:
            self.subscriber_task.cancel()
            await asyncio.gather(self.subscriber_task, return_exceptions=True)
        await self._close_redis()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def publish(self, event: dict[str, Any]) -> None:
        message = json.dumps(event)
        if self.redis is None:
            await self.broadcast(message)
            return
        try:
            await self.redis.publish(QUEUE_CHANNEL, message)
        except Exception:
            await self.broadcast(message)

    async def broadcast(self, message: str) -> None:
        disconnected: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)

    async def _subscribe(self) -> None:
        if self.redis is None:
            return
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(QUEUE_CHANNEL)
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    await self.broadcast(str(message["data"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def _close_redis(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
            self.redis = None

