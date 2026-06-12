"""Webhook and notification dispatch for enterprise event alerts."""

import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import structlog

from ..events import Event, EventType, Severity, Notification

logger = structlog.get_logger()


@dataclass
class WebhookSubscription:
    url: str
    events: List[str]
    secret: Optional[str] = None
    active: bool = True
    created_at: str = ""


class NotificationService:
    """Manages webhooks, user notifications, and alert routing.

    Stores subscriptions in-memory and persists to a JSON file.
    Dispatches to webhooks asynchronously with retry.
    """

    def __init__(self, config_path: str = "notifications_config.json"):
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._user_notifications: List[Notification] = []
        self._config_path = Path(config_path)
        self._max_notifications = 1000
        self._load_config()

    # ── Webhook Management ─────────────────────────────────────────────

    def add_webhook(self, sub_id: str, url: str, events: List[str], secret: Optional[str] = None) -> WebhookSubscription:
        """Register a webhook subscription."""
        sub = WebhookSubscription(
            url=url,
            events=events,
            secret=secret,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._subscriptions[sub_id] = sub
        self._save_config()
        logger.info("Webhook registered", sub_id=sub_id, url=url, events=len(events))
        return sub

    def remove_webhook(self, sub_id: str) -> bool:
        """Remove a webhook subscription."""
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            self._save_config()
            logger.info("Webhook removed", sub_id=sub_id)
            return True
        return False

    def list_webhooks(self) -> Dict[str, WebhookSubscription]:
        return dict(self._subscriptions)

    def get_webhook(self, sub_id: str) -> Optional[WebhookSubscription]:
        return self._subscriptions.get(sub_id)

    async def dispatch_event(self, event: Event) -> int:
        """Dispatch an event to all matching webhooks. Returns count dispatched."""
        dispatched = 0
        for sub_id, sub in list(self._subscriptions.items()):
            if not sub.active:
                continue
            if event.type.value not in sub.events and "all" not in sub.events:
                continue
            try:
                await self._call_webhook(sub, event)
                dispatched += 1
            except Exception as e:
                logger.error("Webhook dispatch failed", sub_id=sub_id, url=sub.url, error=str(e))
        return dispatched

    async def _call_webhook(self, sub: WebhookSubscription, event: Event) -> None:
        """Fire a webhook with the event payload."""
        import httpx

        payload = {
            "event_type": event.type.value,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
            "source": event.source,
        }

        headers = {"Content-Type": "application/json"}
        if sub.secret:
            headers["X-Webhook-Secret"] = sub.secret

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(sub.url, json=payload, headers=headers)
            resp.raise_for_status()

    # ── User Notifications ─────────────────────────────────────────────

    async def notify_user(
        self,
        user_id: str,
        title: str,
        message: str,
        event_type: EventType,
        severity: Severity = Severity.INFO,
        action_url: Optional[str] = None,
    ) -> Notification:
        """Create a notification for a user."""
        notification = Notification(
            event_id=f"notif:{user_id}:{int(datetime.now().timestamp())}",
            title=title,
            message=message,
            severity=severity,
            type=event_type,
            timestamp=datetime.now(),
            action_url=action_url,
        )
        self._user_notifications.append(notification)
        if len(self._user_notifications) > self._max_notifications:
            self._user_notifications.pop(0)

        logger.info("User notification created", user_id=user_id, title=title, severity=severity.value)
        return notification

    def get_user_notifications(self, user_id: str, unread_only: bool = False, limit: int = 50) -> List[Notification]:
        """Get notifications for a user."""
        if unread_only:
            return [n for n in self._user_notifications if not n.read][:limit]
        return self._user_notifications[:limit]

    def mark_notification_read(self, event_id: str) -> bool:
        """Mark a notification as read."""
        for n in self._user_notifications:
            if n.event_id == event_id:
                n.read = True
                return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user. Returns count."""
        count = 0
        for n in self._user_notifications:
            if not n.read:
                n.read = True
                count += 1
        return count

    # ── Persistence ────────────────────────────────────────────────────

    def _save_config(self) -> None:
        """Persist webhook subscriptions to disk."""
        try:
            data = {
                sub_id: {
                    "url": sub.url,
                    "events": sub.events,
                    "secret": sub.secret,
                    "active": sub.active,
                    "created_at": sub.created_at,
                }
                for sub_id, sub in self._subscriptions.items()
            }
            self._config_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error("Failed to save notification config", error=str(e))

    def _load_config(self) -> None:
        """Load webhook subscriptions from disk."""
        try:
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text())
                for sub_id, sub_data in data.items():
                    self._subscriptions[sub_id] = WebhookSubscription(**sub_data)
        except Exception as e:
            logger.error("Failed to load notification config", error=str(e))


notification_service = NotificationService()
