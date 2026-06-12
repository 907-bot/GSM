import json
import asyncio
import structlog
from typing import Callable, Coroutine, Any, Optional
from datetime import datetime
from redis import asyncio as aioredis
from .config import settings
from .events import Event, EventType, Severity, Notification

logger = structlog.get_logger()


class EventBus:
    """Async event bus with Redis pub/sub for cross-process broadcasting."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._local_handlers: dict[str, list[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            try:
                self._redis = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("EventBus connected to Redis")
            except Exception as e:
                logger.warning("EventBus Redis unavailable, using local-only mode", error=str(e))
                self._redis = None  # local-only mode
        return self._redis

    async def publish(self, event: Event) -> None:
        """Publish an event to Redis pub/sub and local handlers."""
        payload = event.model_dump_json()

        # Local handlers always fire
        await self._dispatch_local(event)

        # Redis broadcast
        try:
            redis = await self._ensure_redis()
            if redis:
                channel = f"gsm:events:{event.room}"
                await redis.publish(channel, payload)
        except Exception as e:
            logger.debug("Redis publish failed (non-fatal)", error=str(e))

    async def subscribe(
        self,
        room: str,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a local handler for a room."""
        if room not in self._local_handlers:
            self._local_handlers[room] = []
        self._local_handlers[room].append(handler)

    async def unsubscribe(self, room: str, handler: Callable) -> None:
        """Remove a local handler."""
        handlers = self._local_handlers.get(room, [])
        if handler in handlers:
            handlers.remove(handler)

    async def _dispatch_local(self, event: Event) -> None:
        """Dispatch event to all matching local handlers."""
        handlers = self._local_handlers.get("all", []) + self._local_handlers.get(event.room, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error("Event handler failed", error=str(e), event_type=event.type.value)

    async def _listen_redis(self) -> None:
        """Background task: listen to Redis pub/sub and forward to local handlers."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return

            self._pubsub = redis.pubsub()
            rooms = ["all", "dashboard", "discovery", "graph", "pipeline"]
            for room in rooms:
                await self._pubsub.subscribe(f"gsm:events:{room}")

            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = Event.model_validate_json(message["data"])
                    await self._dispatch_local(event)
                except Exception as e:
                    logger.error("Failed to parse Redis event", error=str(e))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis listener stopped", error=str(e))

    async def start(self) -> None:
        """Start the background Redis listener."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_redis())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the background Redis listener."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe()
        if self._redis:
            await self._redis.close()
        logger.info("EventBus stopped")

    # --- Convenience publishers ---

    async def agent_event(self, domain: str, event_type: EventType, **data) -> None:
        await self.publish(Event(
            type=event_type,
            data={"domain": domain, **data},
            room="discovery",
            source=f"agent.{domain}",
        ))

    async def contradiction_detected(self, contradiction) -> None:
        await self.publish(Event(
            type=EventType.CONTRADICTION_DETECTED,
            data={
                "id": str(contradiction.id),
                "type": contradiction.contradiction_type,
                "confidence": contradiction.confidence,
                "explanation": contradiction.explanation,
            },
            severity=Severity.WARNING,
            room="discovery",
        ))

    async def bottleneck_found(self, bottleneck) -> None:
        await self.publish(Event(
            type=EventType.BOTTLENECK_FOUND,
            data={
                "field": bottleneck.field,
                "bottleneck": bottleneck.major_bottleneck,
                "confidence": bottleneck.confidence,
                "description": bottleneck.description,
            },
            severity=Severity.INFO,
            room="discovery",
        ))

    async def hypothesis_generated(self, hypothesis) -> None:
        await self.publish(Event(
            type=EventType.HYPOTHESIS_GENERATED,
            data={
                "id": str(hypothesis.id),
                "text": hypothesis.hypothesis_text,
                "confidence": hypothesis.confidence,
                "concepts": hypothesis.related_concepts,
            },
            severity=Severity.INFO,
            room="discovery",
        ))

    async def pipeline_update(self, stage: str, status: str, **metrics) -> None:
        await self.publish(Event(
            type=EventType.PIPELINE_STAGE_UPDATE,
            data={"stage": stage, "status": status, **metrics},
            room="pipeline",
        ))

    async def graph_relationship(self, source: str, target: str, rel_type: str) -> None:
        await self.publish(Event(
            type=EventType.GRAPH_RELATIONSHIP_CREATED,
            data={"source": source, "target": target, "type": rel_type},
            room="graph",
        ))

    async def system_metrics(self, **metrics) -> None:
        await self.publish(Event(
            type=EventType.SYSTEM_METRICS,
            data=metrics,
            room="dashboard",
        ))


# Singleton
event_bus = EventBus()
