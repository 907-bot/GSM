import json
import asyncio
from uuid import UUID
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import structlog
import uuid

from ..config import settings
from ..database import db
from ..models import (
    Paper, Finding, Contradiction, Bottleneck,
    Hypothesis, ExperimentRecommendation, EvidenceItem,
)
from ..agents import get_all_agents
from ..agents.sources import HuggingFacePapersSource
from ..agents.sources_extended import BioRxivSource, MedRxivSource, CORESource
from ..agents.citation_agent import citation_agent
from ..engines import (
    ReplayEngine,
    ContradictionEngine,
    BottleneckEngine,
    HypothesisGenerator,
    GraphDiscoveryEngine,
    NoveltyEngine,
    ScientificExtractor,
)
from ..engines.novelty import novelty_engine
from ..engines.extraction import scientific_extractor
from ..memory import EpisodicMemory, SemanticMemory
from ..memory.graph_schema import graph_schema
from ..services import embedding_service, llm_service
from ..bus import event_bus
from ..events import Event, EventType
from ..auth.service import auth_service
from ..auth.models import UserCreate, UserLogin, TokenRefresh, UserRole
from ..auth.middleware import require_auth, require_role, optional_user
from ..middleware.rate_limit import RateLimiter
from ..middleware.request_id import RequestIDMiddleware
from ..services.audit import audit_service
from ..services.notifications import notification_service
from ..services.event_queue import event_queue
from ..services.retention import retention_service
from .ws import ws_manager

logger = structlog.get_logger()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Global Scientific Memory OS - Continuous Scientific Discovery Platform",
)


@app.on_event("startup")
async def startup():
    """Initialize everything — database, event bus, WebSocket."""
    await db.connect()
    logger.info("Database connected", backend=type(db).__name__)

    await event_bus.start()

    async def forward_to_ws(event: Event) -> None:
        await ws_manager.broadcast(event, room=event.room)

    await event_bus.subscribe("all", forward_to_ws)
    await event_bus.subscribe("dashboard", forward_to_ws)
    await event_bus.subscribe("discovery", forward_to_ws)
    await event_bus.subscribe("graph", forward_to_ws)
    await event_bus.subscribe("pipeline", forward_to_ws)
    logger.info("Event bus wired to WebSocket manager")


@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown — drain connections, stop workers."""
    logger.info("Shutting down gracefully...")
    await event_bus.stop()
    await db.close()
    logger.info("Database connection closed")


# Middleware (order matters: first added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None
    limit: int = 100


class HypothesisRequest(BaseModel):
    context: Optional[Dict[str, Any]] = None
    num_hypotheses: int = 5


class BottleneckRequest(BaseModel):
    field: str
    time_window_days: int = 30


class GraphPathRequest(BaseModel):
    source: str
    target: str
    max_depth: int = 5


class FetchPapersRequest(BaseModel):
    query: str = ""
    max_results: int = Field(default=25, ge=1, le=100)


class AgentSearchRequest(BaseModel):
    domain: Optional[str] = None


class ReplayRequest(BaseModel):
    time_window_days: int = Field(default=7, ge=1, le=365)
    sample_size: int = Field(default=100, ge=1, le=10000)


class DreamRequest(BaseModel):
    duration_minutes: int = Field(default=30, ge=1, le=1440)


class SimilaritySearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=200)
    filter_type: Optional[str] = None


class PaperProcessRequest(BaseModel):
    title: str
    abstract: str = ""
    authors: List[str] = []
    source: str = "manual"
    source_id: str = ""
    categories: List[str] = []
    doi: Optional[str] = None
    published_at: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ContradictionDetectRequest(BaseModel):
    time_window_days: int = Field(default=30, ge=1, le=365)


# Standardized error response
class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Any = None
    request_id: Optional[str] = None


class PaginationParams:
    """Extract and validate pagination from query params."""
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = max(1, min(100, page_size))
        self.offset = (self.page - 1) * self.page_size

    def paginate(self, total: int, data: list) -> dict:
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        return {
            "data": data,
            "pagination": {
                "page": self.page,
                "page_size": self.page_size,
                "total": total,
                "total_pages": total_pages,
                "next": f"?page={self.page + 1}&page_size={self.page_size}" if self.page < total_pages else None,
                "prev": f"?page={self.page - 1}&page_size={self.page_size}" if self.page > 1 else None,
            },
        }


# Request ID middleware via dependency
async def get_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error("Unhandled exception", error=str(exc), request_id=request_id, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="INTERNAL_ERROR",
            message="An unexpected error occurred",
            detail=str(exc) if settings.DEBUG else None,
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request.headers.get("X-Request-ID", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=f"HTTP_{exc.status_code}",
            message=exc.detail,
            request_id=request_id,
        ).model_dump(),
    )


# Initialize engines
replay_engine = ReplayEngine()
contradiction_engine = ContradictionEngine()
bottleneck_engine = BottleneckEngine()
hypothesis_generator = HypothesisGenerator()
graph_engine = GraphDiscoveryEngine()
episodic_memory = EpisodicMemory()
semantic_memory = SemanticMemory()
rate_limiter = RateLimiter()

# In-memory hypothesis store (persisted in DB in production)
_hypothesis_store: Dict[str, Hypothesis] = {}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint — subscribes to 'all' room by default."""
    await ws_manager.handle_websocket(ws, room="all")


@app.websocket("/ws/{room}")
async def websocket_room_endpoint(ws: WebSocket, room: str):
    """WebSocket endpoint with room subscription."""
    await ws_manager.handle_websocket(ws, room=room)


@app.get("/events")
async def sse_endpoint(request: Request, room: str = "all"):
    """Server-Sent Events endpoint — fallback when WebSocket isn't available."""
    async def event_generator():
        queue: asyncio.Queue[Event] = asyncio.Queue()

        async def handler(event: Event) -> None:
            await queue.put(event)

        await event_bus.subscribe(room, handler)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
        finally:
            await event_bus.unsubscribe(room, handler)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    return ws_manager.stats


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health/readiness")
async def readiness():
    """Readiness probe — checks if all backends are reachable."""
    checks = {"api": "up"}

    try:
        await episodic_memory.count_papers()
        checks["qdrant"] = "up"
    except Exception:
        checks["qdrant"] = "down"

    try:
        await semantic_memory.get_statistics()
        checks["neo4j"] = "up"
    except Exception:
        checks["neo4j"] = "down"

    all_up = all(v == "up" for v in checks.values())
    return {
        "status": "ready" if all_up else "degraded",
        "checks": checks,
    }


@app.get("/health/liveness")
async def liveness():
    """Liveness probe — basic process health."""
    return {"status": "alive"}


@app.get("/metrics")
async def metrics(user: Optional[Dict[str, Any]] = Depends(optional_user)):
    """Expose basic application metrics."""
    total_papers = await episodic_memory.count_papers()
    user_count = len((await auth_service.list_users())) if user else 0
    return {
        "papers_total": total_papers,
        "users_total": user_count,
        "uptime_seconds": (datetime.now() - getattr(app.state, "start_time", datetime.now())).seconds,
        "rate_limiter": rate_limiter.stats(),
    }


@app.on_event("startup")
async def _startup():
    """Initialize database, start event queue."""
    # Initialize persistent storage
    await db.connect()
    app.state.start_time = datetime.now()

    logger.info("Database initialized", path="data/gsm_os.db")

    # Start event queue consumer (best-effort, tolerates Redis being down)
    try:
        async def queue_handler(event: Event) -> bool:
            await event_bus._dispatch_local(event)
            return True
        asyncio.create_task(event_queue.start_consumer(queue_handler, concurrency=3))
    except Exception as e:
        logger.warning("Event queue consumer not started (non-fatal)", error=str(e))


# ── Authentication ────────────────────────────────────────────────────


@app.post("/auth/register")
async def register_user(data: UserCreate):
    """Register a new user account."""
    try:
        user = await auth_service.register(data)
        tokens = await auth_service.create_tokens(user)
        await audit_service.log(
            action="user.register",
            actor=user.email,
            detail={"email": user.email, "role": user.role.value},
        )
        return tokens.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/auth/login")
async def login_user(data: UserLogin):
    """Authenticate and receive JWT tokens."""
    user = await auth_service.authenticate(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    tokens = await auth_service.create_tokens(user)
    await audit_service.log(
        action="user.login",
        actor=user.email,
    )
    return tokens.model_dump()


@app.post("/auth/refresh")
async def refresh_token(data: TokenRefresh):
    """Refresh an access token using a refresh token."""
    tokens = await auth_service.refresh_access_token(data.refresh_token)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return tokens.model_dump()


@app.get("/auth/me")
async def get_me(user: Dict[str, Any] = Depends(require_auth)):
    """Get the current authenticated user's profile."""
    db_user = await auth_service.get_user_by_email(user.get("email", ""))
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "email": db_user.email,
        "name": db_user.name,
        "role": db_user.role.value,
        "is_active": db_user.is_active,
        "api_key": db_user.api_key,
        "created_at": db_user.created_at.isoformat(),
        "last_login": db_user.last_login.isoformat() if db_user.last_login else None,
    }


@app.post("/auth/logout")
async def logout_user(user: Dict[str, Any] = Depends(require_auth)):
    """Logout by revoking all refresh tokens."""
    await audit_service.log(
        action="user.logout",
        actor=user.get("email", "unknown"),
    )
    return {"status": "logged_out"}


# ── Admin ─────────────────────────────────────────────────────────────


@app.get("/admin/users")
async def list_users(_: Dict[str, Any] = Depends(require_role([UserRole.ADMIN]))):
    """Admin: list all registered users."""
    users = await auth_service.list_users()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ],
        "total": len(users),
    }


@app.put("/admin/users/{email}/role")
async def update_user_role(
    email: str,
    role: UserRole,
    _: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: change a user's role."""
    user = await auth_service.update_role(email, role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await audit_service.log(
        action="admin.role_update",
        actor="admin",
        detail={"email": email, "new_role": role.value},
    )
    return {"status": "updated", "email": email, "role": role.value}


@app.delete("/admin/users/{email}")
async def deactivate_user(
    email: str,
    _: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: deactivate a user account."""
    ok = await auth_service.deactivate_user(email)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await audit_service.log(
        action="admin.user_deactivate",
        actor="admin",
        detail={"email": email},
    )
    return {"status": "deactivated", "email": email}


# ── Audit & Compliance ────────────────────────────────────────────────


@app.get("/audit/events")
async def get_audit_events(
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: view audit log events."""
    events = await audit_service.get_events(
        limit=limit, offset=offset,
        action_filter=action, actor_filter=actor,
    )
    total = await audit_service.count_events()
    return {
        "events": events,
        "total": total,
        "returned": len(events),
        "offset": offset,
    }


@app.post("/audit/export")
async def export_audit(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: export audit log to file."""
    path = await audit_service.export_to_file(f"audit_logs/export-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    await audit_service.log(
        action="audit.export",
        actor=user.get("email", "unknown"),
        detail={"path": path},
    )
    return {"path": path, "status": "exported"}


# ── Notifications & Webhooks ──────────────────────────────────────────


class WebhookCreateRequest(BaseModel):
    url: str
    events: List[str] = ["all"]
    secret: Optional[str] = None


@app.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Get notifications for the current user."""
    notifications = notification_service.get_user_notifications(
        user.get("user_id", ""),
        unread_only=unread_only,
        limit=limit,
    )
    return {
        "notifications": [
            {
                "id": n.event_id,
                "title": n.title,
                "message": n.message,
                "severity": n.severity.value,
                "type": n.type.value,
                "timestamp": n.timestamp.isoformat(),
                "read": n.read,
                "action_url": n.action_url,
            }
            for n in notifications
        ],
        "total": len(notifications),
    }


@app.post("/notifications/{event_id}/read")
async def mark_notification_read(
    event_id: str,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Mark a notification as read."""
    ok = notification_service.mark_notification_read(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "marked_read", "event_id": event_id}


@app.post("/notifications/read-all")
async def mark_all_read(
    user: Dict[str, Any] = Depends(require_auth),
):
    """Mark all notifications as read."""
    count = notification_service.mark_all_read(user.get("user_id", ""))
    return {"status": "all_marked_read", "count": count}


@app.get("/webhooks")
async def list_webhooks(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: list all configured webhooks."""
    webhooks = notification_service.list_webhooks()
    return {
        "webhooks": [
            {
                "id": sub_id,
                "url": sub.url,
                "events": sub.events,
                "active": sub.active,
                "created_at": sub.created_at,
            }
            for sub_id, sub in webhooks.items()
        ],
        "total": len(webhooks),
    }


@app.post("/webhooks")
async def create_webhook(
    request: WebhookCreateRequest,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: register a new webhook."""
    import secrets
    sub_id = f"wh_{secrets.token_hex(8)}"
    sub = notification_service.add_webhook(
        sub_id=sub_id,
        url=request.url,
        events=request.events,
        secret=request.secret,
    )
    await audit_service.log(
        action="webhook.create",
        actor=user.get("email", "unknown"),
        detail={"sub_id": sub_id, "url": request.url},
    )
    return {
        "id": sub_id,
        "url": sub.url,
        "events": sub.events,
        "active": sub.active,
    }


@app.delete("/webhooks/{sub_id}")
async def delete_webhook(
    sub_id: str,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: remove a webhook."""
    ok = notification_service.remove_webhook(sub_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await audit_service.log(
        action="webhook.delete",
        actor=user.get("email", "unknown"),
        detail={"sub_id": sub_id},
    )
    return {"status": "deleted", "sub_id": sub_id}


@app.get("/queue/stats")
async def get_queue_stats(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: view event queue statistics."""
    depth = await event_queue.get_queue_depth("default")
    dlq = await event_queue.get_dlq_messages("default", limit=10)
    return {
        "queue_depth": depth,
        "dlq_count": len(dlq),
        "dlq_samples": [
            {
                "id": m.get("id"),
                "event_type": m.get("event", {}).get("type"),
                "last_error": m.get("last_error"),
                "retry_count": m.get("retry_count"),
                "failed_at": m.get("failed_at"),
            }
            for m in dlq[:5]
        ],
    }


@app.post("/queue/requeue-dlq")
async def requeue_from_dlq(
    message_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: requeue failed events from the dead letter queue."""
    ok = await event_queue.requeue_from_dlq("default", message_id=message_id or "")
    await audit_service.log(
        action="queue.requeue_dlq",
        actor=user.get("email", "unknown"),
        detail={"message_id": message_id or "all"},
    )
    return {"status": "requeued" if ok else "no_messages"}


# ── Data Retention & Lifecycle ────────────────────────────────────────


@app.get("/retention/policies")
async def get_retention_policies(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: view data retention policies."""
    policies = retention_service.get_policies()
    return {
        "policies": [
            {
                "name": p.name,
                "max_age_days": p.max_age_days,
                "min_quality_score": p.min_quality_score,
                "sources_to_keep": p.sources_to_keep,
                "sources_to_purge": p.sources_to_purge,
                "archive_inactive_days": p.archive_inactive_days,
                "action": p.action,
            }
            for p in policies.values()
        ]
    }


@app.get("/retention/policies/{policy_name}")
async def get_retention_policy(
    policy_name: str,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: get a specific retention policy."""
    policies = retention_service.get_policies()
    policy = policies.get(policy_name)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {
        "name": policy.name,
        "max_age_days": policy.max_age_days,
        "min_quality_score": policy.min_quality_score,
        "sources_to_keep": policy.sources_to_keep,
        "sources_to_purge": policy.sources_to_purge,
        "archive_inactive_days": policy.archive_inactive_days,
        "action": policy.action,
    }


class PolicyCreateRequest(BaseModel):
    name: str
    max_age_days: Optional[int] = None
    min_quality_score: Optional[float] = None
    sources_to_keep: Optional[List[str]] = None
    sources_to_purge: Optional[List[str]] = None
    archive_inactive_days: Optional[int] = None
    action: str = "archive"


@app.post("/retention/policies")
async def create_retention_policy(
    request: PolicyCreateRequest,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: create or update a retention policy."""
    policy = RetentionPolicy(
        name=request.name,
        max_age_days=request.max_age_days,
        min_quality_score=request.min_quality_score,
        sources_to_keep=request.sources_to_keep,
        sources_to_purge=request.sources_to_purge,
        archive_inactive_days=request.archive_inactive_days,
        action=request.action,
    )
    retention_service.set_policy(request.name, policy)
    await audit_service.log(
        action="retention.policy_create",
        actor=user.get("email", "unknown"),
        detail={"name": request.name, "action": request.action},
    )
    return {"status": "created", "name": request.name}


@app.delete("/retention/policies/{policy_name}")
async def delete_retention_policy(
    policy_name: str,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: delete a custom retention policy."""
    ok = retention_service.remove_policy(policy_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Policy not found or is protected")
    await audit_service.log(
        action="retention.policy_delete",
        actor=user.get("email", "unknown"),
        detail={"name": policy_name},
    )
    return {"status": "deleted", "name": policy_name}


@app.post("/retention/apply")
async def apply_retention_policies(
    dry_run: bool = False,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: apply retention policies to all papers.

    Use dry_run=true to preview without making changes.
    """
    stats = await retention_service.apply_policies(dry_run=dry_run)
    await audit_service.log(
        action="retention.apply",
        actor=user.get("email", "unknown"),
        detail={"dry_run": dry_run, "stats": stats},
    )
    return {
        "status": "dry_run" if dry_run else "applied",
        "stats": stats,
    }


@app.get("/retention/archived")
async def list_archived_papers(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: list all archived papers."""
    archived = await retention_service.list_archived()
    return {"archived": archived, "total": len(archived)}


@app.post("/retention/restore/{paper_id}")
async def restore_archived_paper(
    paper_id: str,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: restore an archived paper back to Qdrant."""
    ok = await retention_service.restore_from_archive(paper_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Archived paper not found")
    await audit_service.log(
        action="retention.restore",
        actor=user.get("email", "unknown"),
        detail={"paper_id": paper_id},
    )
    return {"status": "restored", "paper_id": paper_id}


@app.get("/admin/backup")
async def trigger_backup(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: trigger an on-demand backup of all data stores.

    Returns instructions for manual backup. Production should use
    the scheduled cron job via scripts/backup.sh.
    """
    await audit_service.log(
        action="admin.backup_trigger",
        actor=user.get("email", "unknown"),
    )
    return {
        "status": "triggered",
        "message": "Run ./scripts/backup.sh for full backup or configure cron with ./scripts/backup_scheduler.sh install",
        "scripts": {
            "backup": "./scripts/backup.sh",
            "scheduler": "./scripts/backup_scheduler.sh install",
        },
    }


@app.get("/admin/backup/list")
async def list_backups(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Admin: list available backups."""
    import glob
    import os

    backup_dir = "backups"
    backups = []
    if os.path.isdir(backup_dir):
        for d in sorted(os.listdir(backup_dir), reverse=True):
            full_path = os.path.join(backup_dir, d)
            if os.path.isdir(full_path):
                size = sum(
                    os.path.getsize(os.path.join(dirpath, f))
                    for dirpath, _, filenames in os.walk(full_path)
                    for f in filenames
                )
                backups.append({
                    "id": d,
                    "size_bytes": size,
                    "size_human": f"{size / 1024 / 1024:.1f} MB" if size > 0 else "0 B",
                    "created_at": datetime.fromtimestamp(os.path.getctime(full_path)).isoformat(),
                })
    return {"backups": backups, "total": len(backups)}


# ── Search & Processing ───────────────────────────────────────────────


@app.post("/search/papers")
async def search_papers(request: SearchRequest):
    """Search for papers across research sources."""
    agents = get_all_agents()
    all_papers = []
    
    for agent in agents:
        try:
            papers = await agent.search_papers(
                request.query,
                sources=request.sources,
                limit=request.limit // len(agents),
            )
            all_papers.extend(papers)
        except Exception as e:
            logger.error("Search failed", agent=agent.domain, error=str(e))
    
    return {
        "query": request.query,
        "papers": all_papers[:request.limit],
        "total": len(all_papers),
    }


@app.post("/search/similar")
async def search_similar(request: SimilaritySearchRequest):
    """Search for similar items in episodic memory."""
    embedding = await embedding_service.embed_text(request.query)
    results = await episodic_memory.search_similar(
        embedding,
        limit=request.limit,
        filter_type=request.filter_type,
    )
    
    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


@app.post("/process/paper")
async def process_paper(
    request: PaperProcessRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Process and store a paper."""
    from ..agents.research_agent import BaseResearchAgent
    
    agent = BaseResearchAgent(domain="general", keywords=[])
    paper = await agent.process_paper(request.model_dump())
    
    if paper:
        await audit_service.log(
            action="paper.process",
            actor=user.get("email", "unknown"),
            detail={"title": request.title[:80], "paper_id": str(paper.id)},
        )
        return {
            "status": "success",
            "paper_id": str(paper.id),
            "message": "Paper processed and stored",
        }
    else:
        raise HTTPException(status_code=400, detail="Failed to process paper")


@app.post("/replay/run")
async def run_replay(
    request: ReplayRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Run the scientific replay system."""
    result = await replay_engine.replay_memories(
        time_window_days=request.time_window_days,
        sample_size=request.sample_size,
    )
    await audit_service.log(
        action="replay.run",
        actor=user.get("email", "unknown"),
        detail={"time_window_days": request.time_window_days},
    )
    return result


@app.post("/replay/dream")
async def run_dream(
    request: DreamRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Run the digital dreaming cycle."""
    result = await replay_engine.dream(duration_minutes=request.duration_minutes)
    await audit_service.log(
        action="replay.dream",
        actor=user.get("email", "unknown"),
    )
    return result


@app.post("/contradictions/detect")
async def detect_contradictions(findings: List[Finding]):
    """Detect contradictions between findings."""
    contradictions = await contradiction_engine.detect_contradictions(findings)
    return {
        "contradictions": contradictions,
        "total": len(contradictions),
    }


@app.get("/contradictions/summary")
async def get_contradiction_summary():
    """Get a summary of detected contradictions."""
    return await contradiction_engine.get_contradiction_summary()


@app.post("/bottlenecks/detect")
async def detect_bottlenecks(
    request: BottleneckRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Detect bottlenecks in a scientific field."""
    bottlenecks = await bottleneck_engine.detect_bottlenecks(
        request.field,
        request.time_window_days,
    )
    await audit_service.log(
        action="bottlenecks.detect",
        actor=user.get("email", "unknown"),
        detail={"field": request.field},
    )
    return {
        "field": request.field,
        "bottlenecks": bottlenecks,
        "total": len(bottlenecks),
    }


@app.get("/bottlenecks/summary/{field}")
async def get_bottleneck_summary(field: str):
    """Get a summary of bottlenecks in a field."""
    return await bottleneck_engine.get_bottleneck_summary(field)


@app.post("/hypotheses/generate")
async def generate_hypotheses(
    request: HypothesisRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Generate scientific hypotheses with full evidence citations."""
    hypotheses = await hypothesis_generator.generate_hypotheses(
        request.context,
        request.num_hypotheses,
    )
    # Store in memory for evidence lookup
    for h in hypotheses:
        _hypothesis_store[str(h.id)] = h
    await audit_service.log(
        action="hypotheses.generate",
        actor=user.get("email", "unknown"),
    )
    return {
        "hypotheses": [h.model_dump() for h in hypotheses],
        "total": len(hypotheses),
    }


@app.get("/hypotheses/{hypothesis_id}/evidence")
async def get_hypothesis_evidence(
    hypothesis_id: str,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Get the full evidence trail for a hypothesis with paper metadata."""
    hypothesis = _hypothesis_store.get(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return {
        "hypothesis_id": hypothesis_id,
        "hypothesis_text": hypothesis.hypothesis_text,
        "confidence": hypothesis.confidence,
        "source_category": hypothesis.source_category,
        "evidence_count": len(hypothesis.evidence_items),
        "evidence": [e.model_dump() for e in hypothesis.evidence_items],
        "supporting_paper_ids": [str(pid) for pid in hypothesis.supporting_evidence],
    }


@app.post("/hypotheses/evaluate/{hypothesis_id}")
async def evaluate_hypothesis(
    hypothesis_id: str,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Evaluate a hypothesis — searches for additional evidence papers."""
    hypothesis = _hypothesis_store.get(hypothesis_id)
    if not hypothesis:
        # Generate a temporary evaluation
        hypothesis = Hypothesis(
            id=UUID(hypothesis_id),
            hypothesis_text="One-shot evaluation — hypothesis not previously generated.",
            confidence=0.5,
        )

    evaluation = await hypothesis_generator.evaluate_hypothesis(hypothesis)
    _hypothesis_store[hypothesis_id] = hypothesis

    await audit_service.log(
        action="hypotheses.evaluate",
        actor=user.get("email", "unknown"),
        resource=hypothesis_id,
    )
    return evaluation


@app.post("/hypotheses/experiment")
async def create_experiment_recommendation(
    hypothesis_id: str,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Create an experiment recommendation with evidence references."""
    hypothesis = _hypothesis_store.get(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found. Generate hypotheses first.")

    recommendation = await hypothesis_generator.create_experiment_recommendation(hypothesis)

    await audit_service.log(
        action="hypotheses.experiment",
        actor=user.get("email", "unknown"),
        resource=hypothesis_id,
    )
    return recommendation.model_dump()


@app.post("/graph/discover/path")
async def discover_path(request: GraphPathRequest):
    """Discover hidden paths between concepts."""
    paths = await graph_engine.discover_hidden_paths(
        request.source,
        request.target,
        request.max_depth,
    )
    return {
        "source": request.source,
        "target": request.target,
        "paths": paths,
        "total": len(paths),
    }


@app.get("/graph/clusters/emerging")
async def detect_emerging_clusters():
    """Detect emerging concept clusters."""
    clusters = await graph_engine.detect_emerging_clusters()
    return {
        "clusters": clusters,
        "total": len(clusters),
    }


@app.get("/graph/missing-links")
async def find_missing_links():
    """Find potential missing links in the knowledge graph."""
    links = await graph_engine.find_missing_links()
    return {
        "missing_links": links,
        "total": len(links),
    }


@app.get("/graph/health")
async def analyze_graph_health():
    """Analyze the health of the knowledge graph."""
    return await graph_engine.analyze_graph_health()


@app.get("/graph/visualize/{concept}")
async def visualize_concept_graph(concept: str, depth: int = 2):
    """Generate visualization data for a concept."""
    return await graph_engine.visualize_subgraph(concept, depth)


@app.get("/memory/statistics")
async def get_memory_statistics():
    """Get statistics about the memory systems."""
    episodic_stats = {
        "collection": settings.QDRANT_COLLECTION,
        "status": "active",
    }
    
    semantic_stats = await semantic_memory.get_statistics()
    
    return {
        "episodic": episodic_stats,
        "semantic": semantic_stats,
    }


@app.post("/agents/search")
async def run_agent_search(
    request: AgentSearchRequest,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN, UserRole.RESEARCHER])),
):
    """Run search cycle for agents."""
    agents = get_all_agents()
    results = []
    
    for agent in agents:
        if request.domain and agent.domain != request.domain:
            continue
        
        try:
            result = await agent.run_search_cycle()
            results.append(result)
        except Exception as e:
            logger.error("Agent search failed", agent=agent.domain, error=str(e))
            results.append({
                "domain": agent.domain,
                "status": "failed",
                "error": str(e),
            })
    
    await audit_service.log(
        action="agents.search",
        actor=user.get("email", "unknown"),
        detail={"domain": request.domain},
    )
    
    return {
        "results": results,
        "total": len(results),
    }


# ── Paper Browser / Research Assistant ──────────────────────────────


@app.get("/papers")
async def list_papers(
    page: int = 1,
    page_size: int = 20,
    query: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    quality_min: Optional[float] = None,
    author: Optional[str] = None,
    sort_by: str = "published_at",
    sort_order: str = "desc",
    user: Optional[Dict[str, Any]] = Depends(optional_user),
):
    """List/search papers with filtering, sorting, and pagination."""
    pagination = PaginationParams(page, page_size)

    papers, total = await episodic_memory.search_papers(
        query=query or "",
        source=source,
        category=category,
        date_from=date_from,
        date_to=date_to,
        quality_min=quality_min,
        author=author,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=pagination.page_size,
        offset=pagination.offset,
    )

    return pagination.paginate(total, papers)


class PaperUpdateRequest(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    doi: Optional[str] = None
    published_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.put("/papers/{paper_id}")
async def update_paper(
    paper_id: str,
    request: PaperUpdateRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Update a paper's metadata fields."""
    existing = await episodic_memory.get_paper(paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")

    payload = dict(existing.get("payload", {}) or {})
    update_data = request.model_dump(exclude_none=True)
    payload.update(update_data)

    ok = await episodic_memory.update_paper(paper_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update paper")

    await audit_service.log(
        action="paper.update",
        actor=user.get("email", "unknown"),
        resource=paper_id,
        detail={"fields": list(update_data.keys())},
    )
    return {"status": "updated", "paper_id": paper_id}


@app.delete("/papers/{paper_id}")
async def delete_paper(
    paper_id: str,
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN, UserRole.RESEARCHER])),
):
    """Permanently delete a paper from memory."""
    existing = await episodic_memory.get_paper(paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")

    ok = await episodic_memory.delete_paper(paper_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete paper")

    await audit_service.log(
        action="paper.delete",
        actor=user.get("email", "unknown"),
        resource=paper_id,
    )
    return {"status": "deleted", "paper_id": paper_id}


@app.post("/papers/{paper_id}/archive")
async def archive_paper(
    paper_id: str,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Soft-delete a paper by marking it as archived."""
    existing = await episodic_memory.get_paper(paper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Paper not found")

    ok = await episodic_memory.archive_paper(paper_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to archive paper")

    await audit_service.log(
        action="paper.archive",
        actor=user.get("email", "unknown"),
        resource=paper_id,
    )
    return {"status": "archived", "paper_id": paper_id}


@app.get("/export/papers")
async def export_papers(
    format: str = "json",
    query: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 1000,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Export papers as JSON or CSV for compliance and data sharing."""
    papers, total = await episodic_memory.search_papers(
        query=query or "",
        source=source,
        category=category,
        limit=limit,
    )

    export_data = []
    for p in papers:
        payload = p.get("payload", {}) or {}
        export_data.append({
            "id": p.get("id"),
            "title": payload.get("title", ""),
            "abstract": payload.get("abstract", ""),
            "authors": ", ".join(payload.get("authors", []) or []),
            "source": payload.get("source", ""),
            "doi": payload.get("doi", ""),
            "published_at": payload.get("published_at", ""),
            "categories": ", ".join(payload.get("categories", []) or []),
            "quality_score": payload.get("quality_score"),
            "source_reliability": (payload.get("provenance") or {}).get("source_reliability"),
        })

    await audit_service.log(
        action="papers.export",
        actor=user.get("email", "unknown"),
        detail={"format": format, "count": len(export_data)},
    )

    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=papers_export.csv"},
        )

    return {"papers": export_data, "total": len(export_data), "exported_at": datetime.now().isoformat()}


@app.get("/papers/{paper_id}")
async def get_paper(paper_id: str):
    """Get a single paper's detail."""
    paper = await episodic_memory.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@app.get("/papers/{paper_id}/summarize")
async def summarize_paper(paper_id: str):
    """SSE-stream a summary of the paper as the user reads."""
    paper = await episodic_memory.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    title = (paper.get("payload") or {}).get("title", "Untitled")
    abstract = (paper.get("payload") or {}).get("abstract", "")

    async def stream_summary():
        messages = [
            {
                "role": "system",
                "content": "You are a research assistant. Summarize the following scientific paper in 3-5 clear, concise sentences. Focus on: what problem it solves, the method used, key findings, and significance.",
            },
            {
                "role": "user",
                "content": f"Title: {title}\n\nAbstract: {abstract}\n\nProvide a concise summary.",
            },
        ]
        async for token in llm_service.chat_stream(
            messages, temperature=0.3, max_tokens=400
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_summary(), media_type="text/event-stream")


@app.get("/papers/{paper_id}/keyterms")
async def extract_keyterms(paper_id: str):
    """Extract key scientific terms with definitions from a paper."""
    paper = await episodic_memory.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    title = (paper.get("payload") or {}).get("title", "Untitled")
    abstract = (paper.get("payload") or {}).get("abstract", "")

    prompt = (
        "Extract the 5-10 most important scientific key terms from this paper. "
        "For each term, provide a brief definition in plain language.\n\n"
        f"Title: {title}\n\nAbstract: {abstract}\n\n"
        "Respond with a JSON array of objects with keys: 'term', 'definition'."
    )
    try:
        result = await llm_service.generate(prompt, temperature=0.2, max_tokens=800)
        import json as _json
        terms = _json.loads(result)
        if isinstance(terms, list):
            return {"paper_id": paper_id, "terms": terms}
    except Exception as e:
        logger.warning("Failed to parse keyterms JSON, returning raw", error=str(e))
        return {"paper_id": paper_id, "terms": [], "raw": result}

    return {"paper_id": paper_id, "terms": []}


@app.get("/papers/{paper_id}/relationships")
async def find_relationships(paper_id: str):
    """Find relationships between this paper and others in memory."""
    paper = await episodic_memory.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    payload = paper.get("payload") or {}
    authors = set(payload.get("authors", []))
    categories = payload.get("categories", [])
    source = payload.get("source", "")

    all_papers = await episodic_memory.list_papers(limit=100)
    relationships = []

    for other in all_papers:
        other_id = str(other.get("id", ""))
        if other_id == paper_id:
            continue
        other_payload = other.get("payload", {})
        other_authors = set(other_payload.get("authors", []))
        other_cats = other_payload.get("categories", [])
        other_source = other_payload.get("source", "")
        other_title = other_payload.get("title", "")

        shared_authors = authors & other_authors
        shared_cats = set(categories) & set(other_cats)

        if shared_authors or shared_cats or other_source == source:
            relationships.append({
                "paper_id": other_id,
                "title": other_title,
                "type": "shared_author" if shared_authors else "shared_category" if shared_cats else "same_source",
                "strength": len(shared_authors) + len(shared_cats),
                "shared_authors": list(shared_authors),
                "shared_categories": list(shared_cats),
            })

    relationships.sort(key=lambda r: r["strength"], reverse=True)
    return {"paper_id": paper_id, "relationships": relationships[:20], "total": len(relationships)}


@app.post("/papers/fetch")
async def fetch_papers(
    request: FetchPapersRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Fetch latest papers from Hugging Face and other sources."""
    hf_source = HuggingFacePapersSource(api_key=settings.HUGGINGFACE_API_KEY)
    all_papers = []

    if request.query:
        papers = await hf_source.search(request.query, max_results=request.max_results)
    else:
        papers = await hf_source.fetch_latest(max_results=request.max_results)
    all_papers.extend(papers)

    await audit_service.log(
        action="papers.fetch",
        actor=user.get("email", "unknown"),
        detail={"query": request.query, "count": len(all_papers)},
    )

    return {
        "papers": all_papers,
        "total": len(all_papers),
        "source": "huggingface",
    }


@app.get("/llm/models")
async def list_llm_models():
    """List all available free LLM models per provider."""
    return {
        "current_provider": settings.DEFAULT_LLM_PROVIDER,
        "current_model": settings.DEFAULT_LLM_MODEL,
        "available_models": llm_service.get_available_models(),
        "providers": {
            "groq": {
                "description": "Free cloud inference — https://console.groq.com/keys",
                "requires_key": True,
                "key_env": "GROQ_API_KEY",
                "configured": bool(settings.GROQ_API_KEY),
            },
            "ollama": {
                "description": "Local inference — fully free, no API key",
                "requires_key": False,
                "endpoint": settings.OLLAMA_ENDPOINT,
            },
            "huggingface": {
                "description": "Free inference API — https://huggingface.co/settings/tokens",
                "requires_key": True,
                "key_env": "HUGGINGFACE_API_KEY",
                "configured": bool(settings.HUGGINGFACE_API_KEY),
            },
        },
    }


class GenerateRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024


@app.post("/llm/generate")
async def generate_text(request: GenerateRequest):
    """Generate text using the configured free LLM provider."""
    try:
        result = await llm_service.generate(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return {
            "provider": settings.DEFAULT_LLM_PROVIDER,
            "model": request.model or settings.DEFAULT_LLM_MODEL,
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Rate Limiting Middleware ──────────────────────────────────────────


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all API requests with standard headers."""
    import time as _time

    endpoint = request.url.path

    skip_paths = ("/health", "/metrics", "/ws", "/events")
    if endpoint.startswith(skip_paths):
        response = await call_next(request)
        return response

    burst = int(getattr(settings, "RATE_LIMIT_DEFAULT_BURST", 20))
    allowed = await rate_limiter.check(request)

    if not allowed:
        remaining, retry_after = await rate_limiter.remaining(request)
        await audit_service.log(
            action="rate_limit.exceeded",
            actor=request.client.host if request.client else "unknown",
            resource=endpoint,
            status="blocked",
            ip_address=request.client.host if request.client else None,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMITED",
                "message": "Too many requests. Please slow down.",
                "retry_after_seconds": int(retry_after),
            },
            headers={
                "X-RateLimit-Limit": str(burst),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(_time.time() + retry_after)),
                "Retry-After": str(int(retry_after)),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(burst)
    response.headers["X-RateLimit-Remaining"] = str(max(0, burst - 1))
    return response


# ── Novelty Engine ────────────────────────────────────────────────────


class NoveltyScoreRequest(BaseModel):
    concepts: List[str] = Field(..., min_items=1, max_items=10)


@app.post("/novelty/score")
async def score_novelty(request: NoveltyScoreRequest):
    """Score how novel a concept combination is (0=well-studied, 1=unexplored)."""
    return await novelty_engine.score_novelty(request.concepts)


@app.get("/novelty/combinations")
async def get_unexplored_combinations(
    min_confidence: float = 0.3,
    max_results: int = 20,
):
    """
    Find unexplored concept combinations — 'what has nobody tried yet'.
    Returns pairs of concepts connected in the graph but with no direct paper.
    """
    combinations = await novelty_engine.find_unexplored_combinations(
        min_confidence=min_confidence,
        max_results=max_results,
    )
    return {"combinations": combinations, "total": len(combinations)}


@app.get("/novelty/drug-repurposing")
async def get_drug_repurposing_candidates(max_results: int = 15):
    """
    Find Drug → Protein → Disease chains where no direct Drug→Disease paper exists.
    These are prime drug repurposing candidates.
    """
    candidates = await novelty_engine.find_drug_repurposing_candidates(max_results=max_results)
    return {"candidates": candidates, "total": len(candidates)}


@app.get("/novelty/rising-concepts")
async def get_rising_concepts(
    time_window_days: int = 30,
    min_papers: int = 3,
):
    """Detect concepts rising in frequency over the past N days."""
    rising = await novelty_engine.detect_rising_concepts(
        time_window_days=time_window_days,
        min_papers=min_papers,
    )
    return {"rising_concepts": rising, "total": len(rising)}


@app.get("/novelty/three-hop-hypotheses")
async def get_three_hop_hypotheses(max_results: int = 10):
    """
    Find A→B→C chains where no direct A→C paper exists.
    These are high-potential hypothesis candidates.
    """
    hypotheses = await novelty_engine.find_three_hop_hypotheses(max_results=max_results)
    return {"hypotheses": hypotheses, "total": len(hypotheses)}


# ── Graph Schema ──────────────────────────────────────────────────────


@app.get("/graph/schema")
async def get_graph_schema():
    """Get full Neo4j node/relation type counts for the knowledge graph."""
    return await graph_schema.get_schema_summary()


@app.post("/graph/schema/initialize")
async def initialize_graph_schema(
    user: Dict[str, Any] = Depends(require_role([UserRole.ADMIN])),
):
    """Initialize all Neo4j constraints and indexes. Safe to run multiple times."""
    result = await graph_schema.initialize()
    await audit_service.log(action="graph.schema_init", actor=user.get("email", "unknown"))
    return result


# ── Scientific Entity Extraction ──────────────────────────────────────


class ExtractRequest(BaseModel):
    paper_id: str
    title: str
    abstract: str
    store_in_graph: bool = True


@app.post("/extract/entities")
async def extract_entities(
    request: ExtractRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Extract scientific entities (methods, datasets, diseases, drugs, etc.) from a paper."""
    entities = await scientific_extractor.extract_from_paper(
        paper_id=request.paper_id,
        title=request.title,
        abstract=request.abstract,
        store_in_graph=request.store_in_graph,
    )
    await audit_service.log(
        action="extract.entities",
        actor=user.get("email", "unknown"),
        resource=request.paper_id,
    )
    return {"paper_id": request.paper_id, "entities": entities}


@app.get("/extract/entities/{paper_id}")
async def get_paper_entities(paper_id: str):
    """Get entities already stored in Neo4j for a given paper."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    entities: Dict[str, List[str]] = {}
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        label_map = {
            "methods": "Method", "datasets": "Dataset",
            "metrics": "Metric", "diseases": "Disease",
            "drugs": "Drug", "concepts": "Concept",
        }
        for key, label in label_map.items():
            result = session.run(
                f"""
                MATCH (p:Paper {{id: $paper_id}})-[]->(e:{label})
                RETURN e.name AS name
                """,
                paper_id=paper_id,
            )
            entities[key] = [r["name"] for r in result if r["name"]]
    driver.close()
    return {"paper_id": paper_id, "entities": entities}


# ── Citation Graph ────────────────────────────────────────────────────


class CitationFetchRequest(BaseModel):
    paper_id: str
    doi: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    direction: str = "both"  # "references", "citations", "both"


@app.post("/papers/{paper_id}/citations/fetch")
async def fetch_paper_citations(
    paper_id: str,
    request: CitationFetchRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Fetch and store citation graph for a paper via Semantic Scholar."""
    result = await citation_agent.fetch_citations(
        paper_id=paper_id,
        doi=request.doi,
        semantic_id=request.semantic_scholar_id,
        limit=request.limit,
        direction=request.direction,
    )
    await audit_service.log(
        action="citations.fetch",
        actor=user.get("email", "unknown"),
        resource=paper_id,
    )
    return result


@app.get("/papers/{paper_id}/citations")
async def get_paper_citations(paper_id: str):
    """Get papers that cite or are cited by this paper from Neo4j."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        refs = session.run(
            "MATCH (p:Paper {id: $id})-[:CITES]->(ref:Paper) RETURN ref.title AS title, ref.id AS id LIMIT 50",
            id=paper_id,
        )
        cits = session.run(
            "MATCH (cit:Paper)-[:CITES]->(p:Paper {id: $id}) RETURN cit.title AS title, cit.id AS id LIMIT 50",
            id=paper_id,
        )
        references = [{"id": r["id"], "title": r["title"]} for r in refs]
        citations = [{"id": r["id"], "title": r["title"]} for r in cits]
    driver.close()
    return {
        "paper_id": paper_id,
        "references": references,
        "citations": citations,
        "reference_count": len(references),
        "citation_count": len(citations),
    }


# ── Paper Draft Generation ────────────────────────────────────────────


class DraftRequest(BaseModel):
    hypothesis: str
    evidence_papers: List[str] = []  # paper titles or abstracts
    sections: List[str] = [
        "abstract", "introduction", "related_work",
        "methodology", "experimental_design",
        "limitations", "future_work",
    ]
    field: str = "general"


@app.post("/papers/draft")
async def generate_paper_draft(
    request: DraftRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """
    Generate a full paper draft outline based on a hypothesis and evidence.
    Streams section by section via SSE.
    """
    evidence_summary = "\n".join(
        f"- {p}" for p in request.evidence_papers[:10]
    )

    async def stream_draft():
        for section in request.sections:
            section_prompts = {
                "abstract": f"Write a scientific abstract (150-250 words) for a paper on: {request.hypothesis}\nEvidence papers:\n{evidence_summary}",
                "introduction": f"Write an Introduction section for a paper on: {request.hypothesis}\nStart with the broader context, then narrow to the specific problem.",
                "related_work": f"Write a Related Work section for: {request.hypothesis}\nReference these papers:\n{evidence_summary}",
                "methodology": f"Propose a detailed Methodology for testing: {request.hypothesis}",
                "experimental_design": f"Design the experiments to validate: {request.hypothesis}\nInclude controls, metrics, and expected outcomes.",
                "limitations": f"Discuss potential Limitations of studying: {request.hypothesis}",
                "future_work": f"Suggest Future Work directions after proving or disproving: {request.hypothesis}",
            }
            prompt = section_prompts.get(section, f"Write the {section} section for: {request.hypothesis}")
            system = "You are a scientific paper writer. Write clearly, precisely, and in academic style."

            yield f"data: {json.dumps({'section': section, 'status': 'generating'})}\n\n"
            section_text = ""
            async for token in llm_service.chat_stream(
                [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=0.4, max_tokens=600,
            ):
                section_text += token
                yield f"data: {json.dumps({'section': section, 'token': token})}\n\n"
            yield f"data: {json.dumps({'section': section, 'status': 'done', 'text': section_text})}\n\n"

        yield "data: [DONE]\n\n"

    await audit_service.log(
        action="papers.draft",
        actor=user.get("email", "unknown"),
        detail={"hypothesis": request.hypothesis[:80]},
    )
    return StreamingResponse(stream_draft(), media_type="text/event-stream")


# ── AI Research Chat ──────────────────────────────────────────────────


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    use_graph_context: bool = True
    max_context_papers: int = 5


@app.post("/llm/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Stream an AI response grounded in the knowledge graph.
    Automatically retrieves relevant papers from Qdrant to augment the prompt.
    """
    context_papers = []
    if request.use_graph_context and request.messages:
        last_user_msg = next(
            (m["content"] for m in reversed(request.messages) if m["role"] == "user"),
            "",
        )
        if last_user_msg:
            try:
                embedding = await embedding_service.embed_text(last_user_msg)
                results = await episodic_memory.search_similar(
                    embedding, limit=request.max_context_papers, filter_type="paper"
                )
                context_papers = [
                    f"- {r.get('payload', {}).get('title', 'Untitled')} "
                    f"({r.get('payload', {}).get('source', '')})"
                    for r in results
                ]
            except Exception:
                pass

    system_prompt = (
        "You are an AI scientist with access to a scientific knowledge graph. "
        "Answer questions about research, hypotheses, and scientific literature. "
        "Be precise, cite evidence where possible, and flag uncertainty."
    )
    if context_papers:
        system_prompt += (
            f"\n\nRelevant papers from the knowledge base:\n"
            + "\n".join(context_papers)
        )

    messages = [{"role": "system", "content": system_prompt}] + request.messages

    async def generate():
        async for token in llm_service.chat_stream(messages, temperature=0.5, max_tokens=1000):
            yield f"data: {json.dumps({'token': token})}\n\n"
        if context_papers:
            yield f"data: {json.dumps({'citations': context_papers})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Reviewer Simulator ────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    title: str
    abstract: str
    methodology: Optional[str] = None
    field: str = "general"
    strictness: str = "moderate"  # "lenient", "moderate", "strict"


@app.post("/review/simulate")
async def simulate_peer_review(
    request: ReviewRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Simulate peer review of a paper using an LLM reviewer agent."""
    strictness_map = {
        "lenient": "a supportive reviewer focused on encouragement",
        "moderate": "a balanced reviewer who gives constructive criticism",
        "strict": "a rigorous reviewer at a top-tier venue like NeurIPS or Nature",
    }
    reviewer_style = strictness_map.get(request.strictness, strictness_map["moderate"])

    prompt = (
        f"You are {reviewer_style}. Review the following paper submission.\n\n"
        f"Title: {request.title}\n\n"
        f"Abstract: {request.abstract}\n\n"
        + (f"Methodology: {request.methodology}\n\n" if request.methodology else "")
        + "Provide:\n"
        "1. Summary (2-3 sentences)\n"
        "2. Strengths (3-5 bullet points)\n"
        "3. Weaknesses (3-5 bullet points)\n"
        "4. Questions for authors (2-3 questions)\n"
        "5. Recommendation: Accept / Major Revision / Minor Revision / Reject\n"
        "6. Confidence score (1-5)\n\n"
        "Be specific and constructive. Reference the abstract directly."
    )

    try:
        review = await llm_service.generate(prompt, temperature=0.4, max_tokens=1200)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Review generation failed: {str(e)}")

    await audit_service.log(
        action="review.simulate",
        actor=user.get("email", "unknown"),
        detail={"title": request.title[:80], "strictness": request.strictness},
    )
    return {
        "title": request.title,
        "field": request.field,
        "strictness": request.strictness,
        "review": review,
    }


# ── Research Roadmap ──────────────────────────────────────────────────


class RoadmapRequest(BaseModel):
    topic: str
    timeframe_years: int = Field(default=3, ge=1, le=10)
    include_gaps: bool = True


@app.post("/roadmap/generate")
async def generate_research_roadmap(
    request: RoadmapRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Generate a structured research roadmap for a topic with gap analysis."""
    # Get relevant papers and gaps from the knowledge graph
    gap_context = ""
    if request.include_gaps:
        try:
            combinations = await novelty_engine.find_unexplored_combinations(max_results=5)
            topic_gaps = [
                c for c in combinations
                if request.topic.lower() in (c.get("concept_a", "") + c.get("concept_b", "")).lower()
            ]
            if topic_gaps:
                gap_context = "\n\nIdentified research gaps:\n" + "\n".join(
                    f"- {g['concept_a']} + {g['concept_b']}: {g.get('recommendation', '')}"
                    for g in topic_gaps
                )
        except Exception:
            pass

    prompt = (
        f"Create a detailed {request.timeframe_years}-year research roadmap for the topic: {request.topic}\n"
        f"{gap_context}\n\n"
        "Structure the roadmap as:\n"
        "## Phase 1: Foundation (Year 1)\n"
        "- Key milestones\n- Required resources\n- Expected outcomes\n\n"
        "## Phase 2: Development (Year 2)\n"
        "- Key milestones\n- Required resources\n- Expected outcomes\n\n"
        f"## Phase 3: Maturation (Year {request.timeframe_years})\n"
        "- Key milestones\n- Required resources\n- Expected outcomes\n\n"
        "## Open Research Questions\n"
        "## Recommended Collaborations\n"
        "## Potential Impact\n\n"
        "Be specific. Reference real techniques, datasets, and existing work where relevant."
    )

    try:
        roadmap = await llm_service.generate(prompt, temperature=0.5, max_tokens=2000)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Roadmap generation failed: {str(e)}")

    await audit_service.log(
        action="roadmap.generate",
        actor=user.get("email", "unknown"),
        detail={"topic": request.topic[:80]},
    )
    return {
        "topic": request.topic,
        "timeframe_years": request.timeframe_years,
        "roadmap": roadmap,
        "gaps_included": request.include_gaps,
    }


# ── Paper Comparison ──────────────────────────────────────────────────


@app.get("/papers/compare")
async def compare_papers(paper_id_a: str, paper_id_b: str):
    """Compare two papers: shared authors, concepts, similarity score, and contradictions."""
    paper_a = await episodic_memory.get_paper(paper_id_a)
    paper_b = await episodic_memory.get_paper(paper_id_b)

    if not paper_a:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id_a} not found")
    if not paper_b:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id_b} not found")

    payload_a = paper_a.get("payload", {}) or {}
    payload_b = paper_b.get("payload", {}) or {}

    authors_a = set(payload_a.get("authors", []))
    authors_b = set(payload_b.get("authors", []))
    cats_a = set(payload_a.get("categories", []))
    cats_b = set(payload_b.get("categories", []))

    shared_authors = list(authors_a & authors_b)
    shared_concepts = list(cats_a & cats_b)

    # Semantic similarity
    similarity = 0.0
    try:
        emb_a = await embedding_service.embed_text(
            f"{payload_a.get('title', '')} {payload_a.get('abstract', '')}"
        )
        emb_b = await embedding_service.embed_text(
            f"{payload_b.get('title', '')} {payload_b.get('abstract', '')}"
        )
        # Cosine similarity
        import math
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        mag_a = math.sqrt(sum(x * x for x in emb_a))
        mag_b = math.sqrt(sum(x * x for x in emb_b))
        similarity = dot / (mag_a * mag_b) if mag_a and mag_b else 0.0
    except Exception:
        pass

    # LLM comparison summary
    comparison_text = ""
    try:
        prompt = (
            f"Compare these two scientific papers:\n\n"
            f"Paper A: {payload_a.get('title', '')}\n{payload_a.get('abstract', '')[:500]}\n\n"
            f"Paper B: {payload_b.get('title', '')}\n{payload_b.get('abstract', '')[:500]}\n\n"
            "In 3-4 sentences: How do they differ? Do they contradict? What does each contribute?"
        )
        comparison_text = await llm_service.generate(prompt, temperature=0.3, max_tokens=300)
    except Exception:
        pass

    return {
        "paper_a": {"id": paper_id_a, "title": payload_a.get("title"), "source": payload_a.get("source")},
        "paper_b": {"id": paper_id_b, "title": payload_b.get("title"), "source": payload_b.get("source")},
        "shared_authors": shared_authors,
        "shared_concepts": shared_concepts,
        "semantic_similarity": round(similarity, 4),
        "similarity_verdict": (
            "Very similar" if similarity > 0.85 else
            "Related" if similarity > 0.6 else
            "Different domains"
        ),
        "comparison_summary": comparison_text,
    }


# ── Extended Source Search ────────────────────────────────────────────


class ExtendedSearchRequest(BaseModel):
    query: str
    sources: List[str] = ["biorxiv", "medrxiv", "core"]
    max_results: int = Field(default=25, ge=1, le=100)


@app.post("/search/extended")
async def search_extended_sources(
    request: ExtendedSearchRequest,
    user: Dict[str, Any] = Depends(require_auth),
):
    """Search bioRxiv, medRxiv, and CORE Open Access sources."""
    source_map = {
        "biorxiv": BioRxivSource(),
        "medrxiv": MedRxivSource(),
        "core": CORESource(api_key=settings.CORE_API_KEY),
    }
    all_papers = []
    source_counts: Dict[str, int] = {}

    for src_name in request.sources:
        source = source_map.get(src_name)
        if not source:
            continue
        try:
            papers = await source.search(request.query, max_results=request.max_results)
            all_papers.extend(papers)
            source_counts[src_name] = len(papers)
        except Exception as e:
            logger.error("Extended source search failed", source=src_name, error=str(e))
            source_counts[src_name] = 0

    await audit_service.log(
        action="search.extended",
        actor=user.get("email", "unknown"),
        detail={"query": request.query, "sources": request.sources},
    )
    return {
        "query": request.query,
        "papers": all_papers,
        "total": len(all_papers),
        "by_source": source_counts,
    }


# ── Graph Schema Startup ──────────────────────────────────────────────

@app.on_event("startup")
async def _initialize_graph_schema():
    """Initialize rich Neo4j schema on startup (idempotent)."""
    try:
        await graph_schema.initialize()
        logger.info("Graph schema initialized on startup")
    except Exception as e:
        logger.warning("Graph schema init failed on startup (non-fatal)", error=str(e))
