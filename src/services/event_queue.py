"""Redis-backed persistent event queue with dead letter queue and retry."""

import json
import asyncio
import time
from typing import Optional, Callable, Awaitable, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone
from redis import asyncio as aioredis
import structlog

from ..config import settings
from ..events import Event

logger = structlog.get_logger()


@dataclass
class QueueMessage:
    id: str
    event: Event
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    enqueued_at: str = ""


class EventQueue:
    """Persistent event queue backed by Redis lists.

    Features:
    - At-least-once delivery via BLPOP + acknowledgements
    - Dead letter queue for failed events
    - Retry with exponential backoff
    - Consumer group awareness
    """

    QUEUE_PREFIX = "gsm:queue"
    DLQ_PREFIX = "gsm:dlq"
    PROCESSING_PREFIX = "gsm:processing"

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            try:
                self._redis = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB + 1,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("EventQueue connected to Redis")
            except Exception as e:
                logger.warning("EventQueue Redis unavailable, using local-only mode", error=str(e))
                self._redis = None
        return self._redis

    async def enqueue(self, event: Event, queue: str = "default") -> bool:
        """Enqueue an event for reliable delivery."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                logger.debug("Queue unavailable, dropping event", event_type=event.type.value)
                return False

            message = QueueMessage(
                id=f"{event.type.value}:{int(time.time() * 1000)}:{id(event)}",
                event=event,
                enqueued_at=datetime.now(timezone.utc).isoformat(),
            )
            payload = json.dumps({
                "id": message.id,
                "event": event.model_dump(),
                "retry_count": message.retry_count,
                "max_retries": message.max_retries,
                "enqueued_at": message.enqueued_at,
            }, default=str)

            queue_key = f"{self.QUEUE_PREFIX}:{queue}"
            await redis.rpush(queue_key, payload)
            logger.debug("Event enqueued", queue=queue, event_id=message.id)
            return True
        except Exception as e:
            logger.error("Failed to enqueue event", error=str(e))
            return False

    async def dequeue(self, queue: str = "default", timeout: int = 5) -> Optional[QueueMessage]:
        """Dequeue the next event (blocking with timeout)."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return None

            queue_key = f"{self.QUEUE_PREFIX}:{queue}"
            processing_key = f"{self.PROCESSING_PREFIX}:{queue}"

            result = await redis.blpop(queue_key, timeout=timeout)
            if not result:
                return None

            _, payload = result
            data = json.loads(payload)
            event = Event(**data["event"])

            # Move to processing set for at-least-once
            await redis.hset(processing_key, data["id"], payload)
            await redis.expire(processing_key, 3600)

            return QueueMessage(
                id=data["id"],
                event=event,
                retry_count=data.get("retry_count", 0),
                max_retries=data.get("max_retries", 3),
                enqueued_at=data.get("enqueued_at", ""),
            )
        except Exception as e:
            logger.error("Failed to dequeue event", error=str(e))
            return None

    async def acknowledge(self, message: QueueMessage, queue: str = "default") -> bool:
        """Acknowledge successful processing of an event."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return False
            processing_key = f"{self.PROCESSING_PREFIX}:{queue}"
            await redis.hdel(processing_key, message.id)
            return True
        except Exception as e:
            logger.error("Failed to acknowledge event", error=str(e))
            return False

    async def requeue(self, message: QueueMessage, queue: str = "default", error: str = "") -> bool:
        """Re-queue a failed event with retry tracking, or send to DLQ."""
        try:
            message.retry_count += 1
            message.last_error = error

            if message.retry_count >= message.max_retries:
                return await self._send_to_dlq(message, queue, error)

            redis = await self._ensure_redis()
            if not redis:
                return False

            queue_key = f"{self.QUEUE_PREFIX}:{queue}"
            processing_key = f"{self.PROCESSING_PREFIX}:{queue}"

            # Exponential backoff: use a delayed queue via ZSET
            backoff_key = f"{self.QUEUE_PREFIX}:backoff:{queue}"
            delay = min(2 ** message.retry_count * 5, 300)  # 10s, 20s, 40s -> max 5min
            retry_at = time.time() + delay

            payload = json.dumps({
                "id": message.id,
                "event": message.event.model_dump(),
                "retry_count": message.retry_count,
                "max_retries": message.max_retries,
                "enqueued_at": message.enqueued_at,
                "last_error": error,
            }, default=str)

            await redis.zadd(backoff_key, {payload: retry_at})
            await redis.hdel(processing_key, message.id)

            logger.info("Event requeued with backoff",
                queue=queue, retry=message.retry_count, delay=delay, error=error)
            return True
        except Exception as e:
            logger.error("Failed to requeue event", error=str(e))
            return False

    async def _send_to_dlq(self, message: QueueMessage, queue: str, error: str) -> bool:
        """Send a failed event to the dead letter queue."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return False

            dlq_key = f"{self.DLQ_PREFIX}:{queue}"
            payload = json.dumps({
                "id": message.id,
                "event": message.event.model_dump(),
                "retry_count": message.retry_count,
                "max_retries": message.max_retries,
                "last_error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }, default=str)

            await redis.lpush(dlq_key, payload)
            processing_key = f"{self.PROCESSING_PREFIX}:{queue}"
            await redis.hdel(processing_key, message.id)

            logger.warning("Event sent to DLQ", queue=queue, event_id=message.id, error=error)
            return True
        except Exception as e:
            logger.error("Failed to send to DLQ", error=str(e))
            return False

    async def get_dlq_messages(self, queue: str = "default", limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve dead letter queue messages for inspection."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return []
            dlq_key = f"{self.DLQ_PREFIX}:{queue}"
            messages = await redis.lrange(dlq_key, 0, limit - 1)
            return [json.loads(m) for m in messages]
        except Exception as e:
            logger.error("Failed to read DLQ", error=str(e))
            return []

    async def requeue_from_dlq(self, queue: str = "default", message_id: str = "") -> bool:
        """Re-queue a message from the DLQ back to the main queue."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return False

            dlq_key = f"{self.DLQ_PREFIX}:{queue}"
            messages = await redis.lrange(dlq_key, 0, -1)

            for msg_payload in messages:
                data = json.loads(msg_payload)
                if not message_id or data.get("id") == message_id:
                    # Reset retry count and re-enqueue
                    data["retry_count"] = 0
                    queue_key = f"{self.QUEUE_PREFIX}:{queue}"
                    await redis.rpush(queue_key, json.dumps(data, default=str))
                    await redis.lrem(dlq_key, 1, msg_payload)
                    logger.info("Re-queued from DLQ", queue=queue, message_id=data["id"])
                    return True
            return False
        except Exception as e:
            logger.error("Failed to requeue from DLQ", error=str(e))
            return False

    async def get_queue_depth(self, queue: str = "default") -> int:
        """Get the current depth of a queue."""
        try:
            redis = await self._ensure_redis()
            if not redis:
                return 0
            queue_key = f"{self.QUEUE_PREFIX}:{queue}"
            return await redis.llen(queue_key)
        except Exception:
            return 0

    async def start_consumer(
        self,
        handler: Callable[[Event], Awaitable[bool]],
        queue: str = "default",
        concurrency: int = 5,
    ) -> None:
        """Start a background consumer that processes events from the queue."""
        if self._running:
            return
        self._running = True
        self._handlers[queue] = handler

        async def _consume():
            semaphore = asyncio.Semaphore(concurrency)
            backoff_key = f"{self.QUEUE_PREFIX}:backoff:{queue}"

            while self._running:
                try:
                    # Process backoff queue (retries due for delivery)
                    redis = await self._ensure_redis()
                    if redis:
                        now = time.time()
                        due = await redis.zrangebyscore(backoff_key, 0, now)
                        for payload in due:
                            queue_key = f"{self.QUEUE_PREFIX}:{queue}"
                            await redis.rpush(queue_key, payload)
                            await redis.zrem(backoff_key, payload)

                    message = await self.dequeue(queue, timeout=3)
                    if not message:
                        continue

                    async with semaphore:
                        try:
                            success = await handler(message.event)
                            if success:
                                await self.acknowledge(message, queue)
                            else:
                                await self.requeue(message, queue, error="Handler returned False")
                        except Exception as e:
                            await self.requeue(message, queue, error=str(e))

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Consumer error", error=str(e))
                    await asyncio.sleep(1)

            logger.info("Event queue consumer stopped", queue=queue)

        self._consumer_task = asyncio.create_task(_consume())
        logger.info("Event queue consumer started", queue=queue, concurrency=concurrency)

    async def stop_consumer(self) -> None:
        """Stop the background consumer."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("Event queue consumer stopped")


event_queue = EventQueue()
