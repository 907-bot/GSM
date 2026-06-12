"""Abstract database backend interface.

Supports both SQLite (single-node) and PostgreSQL (production multi-worker).
Backend is selected via the DATABASE_URL environment variable.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple


class DatabaseBackend(ABC):
    """Abstract interface for all database operations."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    # ── User operations ────────────────────────────────────────────────

    @abstractmethod
    async def create_user(self, user_id: str, email: str, password_hash: str,
                           name: str, role: str, api_key: str) -> bool: ...

    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def list_users(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def update_user_login(self, user_id: str) -> None: ...

    @abstractmethod
    async def update_user_role(self, email: str, role: str) -> bool: ...

    @abstractmethod
    async def deactivate_user(self, email: str) -> bool: ...

    # ── Paper operations ───────────────────────────────────────────────

    @abstractmethod
    async def upsert_paper(self, paper_id: str, title: str, abstract: str,
                            authors: list, doi: Optional[str], source: str,
                            source_id: str, url: Optional[str],
                            published_at: Optional[str], categories: list,
                            citations_count: int, quality_score: Optional[float],
                            provenance: Optional[dict], metadata: dict) -> None: ...

    @abstractmethod
    async def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def search_papers(self, query: str = "", source: Optional[str] = None,
                             category: Optional[str] = None,
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None,
                             quality_min: Optional[float] = None,
                             author: Optional[str] = None,
                             sort_by: str = "published_at",
                             sort_order: str = "desc", limit: int = 50,
                             offset: int = 0) -> Tuple[List[Dict[str, Any]], int]: ...

    @abstractmethod
    async def count_papers(self) -> int: ...

    @abstractmethod
    async def archive_paper(self, paper_id: str) -> bool: ...

    @abstractmethod
    async def delete_paper(self, paper_id: str) -> bool: ...

    @abstractmethod
    async def get_papers_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def unarchive_paper(self, paper_id: str) -> bool: ...

    @abstractmethod
    async def get_papers_for_retention(self, limit: int = 1000) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def get_archived_papers(self) -> List[Dict[str, Any]]: ...

    # ── Audit operations ───────────────────────────────────────────────

    @abstractmethod
    async def create_audit_event(self, timestamp: str, action: str, actor: str,
                                   resource: Optional[str], detail: str,
                                   status: str, ip_address: Optional[str]) -> None: ...

    @abstractmethod
    async def get_audit_events(self, limit: int = 100, offset: int = 0,
                                action_filter: Optional[str] = None,
                                actor_filter: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def count_audit_events(self) -> int: ...

    @abstractmethod
    async def export_audit_events(self) -> List[Dict[str, Any]]: ...

    # ── Webhook operations ─────────────────────────────────────────────

    @abstractmethod
    async def create_webhook(self, wh_id: str, url: str, events: list,
                              secret: Optional[str]) -> None: ...

    @abstractmethod
    async def get_webhook(self, wh_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def list_webhooks(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def delete_webhook(self, wh_id: str) -> bool: ...

    @abstractmethod
    async def save_hypothesis(self, hypothesis_id: str, hypothesis_text: str,
                               confidence: float, supporting_evidence: list,
                               evidence_items: list,
                               suggested_experiments: list,
                               related_concepts: list,
                               source_category: Optional[str],
                               evaluated: bool,
                               evaluation_summary: Optional[str]) -> None: ...

    @abstractmethod
    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    async def list_hypotheses(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]: ...
