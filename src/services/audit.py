"""Audit logging service — all events persisted in SQLite.

Enterprise-grade: immutable trail, filterable, exportable.
Uses the Database layer for storage (no JSON-Lines file).
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import structlog

from ..database import db

logger = structlog.get_logger()


class AuditService:
    """Logs security-relevant events to SQLite for compliance and forensics."""

    async def log(
        self,
        action: str,
        actor: str = "system",
        resource: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
    ) -> None:
        """Record an audit event."""
        import json

        await db.create_audit_event(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            actor=actor,
            resource=resource,
            detail=json.dumps(detail or {}, default=str),
            status=status,
            ip_address=ip_address,
        )
        logger.info("Audit event", action=action, actor=actor, status=status)

    async def get_events(
        self,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit events with optional filtering."""
        import json

        rows = await db.get_audit_events(
            limit=limit,
            offset=offset,
            action_filter=action_filter,
            actor_filter=actor_filter,
        )
        events = []
        for r in rows:
            detail = r.get("detail", "{}")
            events.append({
                "id": r["id"],
                "timestamp": r["timestamp"],
                "action": r["action"],
                "actor": r["actor"],
                "resource": r["resource"],
                "detail": json.loads(detail) if isinstance(detail, str) else detail,
                "status": r["status"],
                "ip_address": r["ip_address"],
            })
        return events

    async def count_events(self) -> int:
        return await db.count_audit_events()

    async def export_to_file(self, path: str) -> str:
        """Export all audit events to a JSON file."""
        import json
        from pathlib import Path

        events = await db.export_audit_events()
        export_path = Path(path)
        with open(export_path, "w") as f:
            json.dump(events, f, default=str, indent=2)
        return str(export_path.resolve())


audit_service = AuditService()
