"""SQLite backend — dev/default. Uses built-in sqlite3 with asyncio.to_thread()."""

import sqlite3
import json
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager
import structlog

from .database_backend import DatabaseBackend

logger = structlog.get_logger()


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class SQLiteBackend(DatabaseBackend):
    """SQLite implementation of DatabaseBackend using asyncio.to_thread."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_db)

    async def close(self) -> None:
        pass  # SQLite connections are short-lived (open/close per query)

    def _init_db(self) -> None:
        conn = _get_conn(self._db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    role TEXT DEFAULT 'viewer',
                    api_key TEXT UNIQUE NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_login TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT DEFAULT '',
                    authors TEXT DEFAULT '[]',
                    doi TEXT,
                    source TEXT DEFAULT 'unknown',
                    source_id TEXT DEFAULT '',
                    url TEXT,
                    published_at TEXT,
                    categories TEXT DEFAULT '[]',
                    citations_count INTEGER DEFAULT 0,
                    quality_score REAL,
                    provenance TEXT,
                    metadata TEXT DEFAULT '{}',
                    archived INTEGER DEFAULT 0,
                    archived_at TEXT,
                    indexed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
                CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
                CREATE INDEX IF NOT EXISTS idx_papers_quality ON papers(quality_score);
                CREATE INDEX IF NOT EXISTS idx_papers_archived ON papers(archived);
                CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_at);
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    resource TEXT,
                    detail TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'success',
                    ip_address TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
                CREATE TABLE IF NOT EXISTS webhooks (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    events TEXT NOT NULL DEFAULT '["all"]',
                    secret TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS retention_policies (
                    name TEXT PRIMARY KEY,
                    max_age_days INTEGER,
                    min_quality_score REAL,
                    sources_to_keep TEXT,
                    sources_to_purge TEXT,
                    archive_inactive_days INTEGER,
                    action TEXT DEFAULT 'archive'
                );
                CREATE TABLE IF NOT EXISTS hypotheses (
                    id TEXT PRIMARY KEY,
                    hypothesis_text TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    supporting_evidence TEXT DEFAULT '[]',
                    evidence_items TEXT DEFAULT '[]',
                    suggested_experiments TEXT DEFAULT '[]',
                    related_concepts TEXT DEFAULT '[]',
                    source_category TEXT,
                    evaluated INTEGER DEFAULT 0,
                    evaluation_summary TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_hypotheses_created ON hypotheses(created_at);
                CREATE INDEX IF NOT EXISTS idx_hypotheses_source ON hypotheses(source_category);
            """)
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def _conn_cm(self):
        conn = _get_conn(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    async def _execute(self, sql: str, params: tuple = ()) -> int:
        def _run():
            conn = _get_conn(self._db_path)
            try:
                conn.execute(sql, params)
                conn.commit()
                return conn.total_changes
            finally:
                conn.close()
        return await asyncio.to_thread(_run)

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        def _run():
            conn = _get_conn(self._db_path)
            try:
                row = conn.execute(sql, params).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        return await asyncio.to_thread(_run)

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        def _run():
            conn = _get_conn(self._db_path)
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
        return await asyncio.to_thread(_run)

    # ── User operations ────────────────────────────────────────────────

    async def create_user(self, user_id: str, email: str, password_hash: str,
                           name: str, role: str, api_key: str) -> bool:
        try:
            await self._execute(
                "INSERT INTO users (id, email, password_hash, name, role, api_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, email, password_hash, name, role, api_key, datetime.now(timezone.utc).isoformat()),
            )
            return True
        except Exception:
            return False

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM users WHERE api_key = ? AND is_active = 1", (api_key,))

    async def list_users(self) -> List[Dict[str, Any]]:
        return await self._fetchall("SELECT * FROM users ORDER BY created_at DESC")

    async def update_user_login(self, user_id: str) -> None:
        await self._execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user_id),
        )

    async def update_user_role(self, email: str, role: str) -> bool:
        c = await self._execute("UPDATE users SET role = ? WHERE email = ?", (role, email.lower().strip()))
        return c > 0

    async def deactivate_user(self, email: str) -> bool:
        c = await self._execute("UPDATE users SET is_active = 0 WHERE email = ?", (email.lower().strip(),))
        return c > 0

    # ── Paper operations ────────────────────────────────────────────────

    async def upsert_paper(self, paper_id: str, title: str, abstract: str,
                            authors: list, doi: Optional[str], source: str,
                            source_id: str, url: Optional[str],
                            published_at: Optional[str], categories: list,
                            citations_count: int, quality_score: Optional[float],
                            provenance: Optional[dict], metadata: dict) -> None:
        await self._execute("""
            INSERT INTO papers (id, title, abstract, authors, doi, source, source_id, url,
                                published_at, categories, citations_count, quality_score,
                                provenance, metadata, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, abstract=excluded.abstract, authors=excluded.authors,
                doi=excluded.doi, source=excluded.source, source_id=excluded.source_id,
                url=excluded.url, published_at=excluded.published_at,
                categories=excluded.categories, citations_count=excluded.citations_count,
                quality_score=excluded.quality_score, provenance=excluded.provenance,
                metadata=excluded.metadata
        """, (
            paper_id, title, abstract, json.dumps(authors), doi, source, source_id, url,
            published_at, json.dumps(categories), citations_count, quality_score,
            json.dumps(provenance) if provenance else None,
            json.dumps(metadata) if metadata else "{}",
            datetime.now(timezone.utc).isoformat(),
        ))

    async def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM papers WHERE id = ?", (paper_id,))

    async def search_papers(self, query: str = "", source: Optional[str] = None,
                             category: Optional[str] = None,
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None,
                             quality_min: Optional[float] = None,
                             author: Optional[str] = None,
                             sort_by: str = "published_at",
                             sort_order: str = "desc", limit: int = 50,
                             offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        conditions = ["archived = 0"]
        params: list = []

        if query:
            conditions.append("(title LIKE ? OR abstract LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if source:
            conditions.append("source = ?")
            params.append(source.lower())

        if category:
            conditions.append("categories LIKE ?")
            params.append(f"%{category}%")

        if date_from:
            conditions.append("published_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("published_at <= ?")
            params.append(date_to)

        if quality_min is not None:
            conditions.append("quality_score >= ?")
            params.append(quality_min)

        if author:
            conditions.append("authors LIKE ?")
            params.append(f"%{author}%")

        where = " AND ".join(conditions)
        valid_sort = {"published_at", "quality_score", "title", "citations_count", "indexed_at"}
        sort_col = sort_by if sort_by in valid_sort else "published_at"
        order = "DESC" if sort_order == "desc" else "ASC"

        count_sql = f"SELECT COUNT(*) as cnt FROM papers WHERE {where}"
        row = await self._fetchone(count_sql, tuple(params))
        total = row["cnt"] if row else 0

        data_sql = f"SELECT * FROM papers WHERE {where} ORDER BY {sort_col} {order} LIMIT ? OFFSET ?"
        rows = await self._fetchall(data_sql, tuple(params) + (limit, offset))

        papers = []
        for r in rows:
            papers.append({
                "id": r["id"],
                "payload": self._paper_payload(r),
            })
        return papers, total

    def _paper_payload(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "paper",
            "title": r["title"],
            "abstract": r.get("abstract", ""),
            "authors": json.loads(r["authors"]) if isinstance(r["authors"], str) else (r["authors"] or []),
            "doi": r.get("doi"),
            "source": r.get("source"),
            "source_id": r.get("source_id"),
            "url": r.get("url"),
            "published_at": r.get("published_at"),
            "categories": json.loads(r["categories"]) if isinstance(r["categories"], str) else (r["categories"] or []),
            "citations_count": r.get("citations_count", 0),
            "quality_score": r.get("quality_score"),
            "provenance": json.loads(r["provenance"]) if r.get("provenance") else None,
            "metadata": json.loads(r["metadata"]) if r.get("metadata") else {},
            "archived": bool(r.get("archived", 0)),
            "archived_at": r.get("archived_at"),
        }

    async def count_papers(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) as cnt FROM papers WHERE archived = 0")
        return row["cnt"] if row else 0

    async def archive_paper(self, paper_id: str) -> bool:
        c = await self._execute(
            "UPDATE papers SET archived = 1, archived_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), paper_id),
        )
        return c > 0

    async def delete_paper(self, paper_id: str) -> bool:
        c = await self._execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        return c > 0

    async def get_papers_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        return await self._fetchall(f"SELECT * FROM papers WHERE id IN ({placeholders})", tuple(ids))

    async def unarchive_paper(self, paper_id: str) -> bool:
        c = await self._execute("UPDATE papers SET archived = 0, archived_at = NULL WHERE id = ?", (paper_id,))
        return c > 0

    async def get_papers_for_retention(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM papers WHERE archived = 0 ORDER BY published_at ASC LIMIT ?", (limit,)
        )

    async def get_archived_papers(self) -> List[Dict[str, Any]]:
        return await self._fetchall(
            "SELECT id, title, archived_at FROM papers WHERE archived = 1 ORDER BY archived_at DESC"
        )

    # ── Audit operations ────────────────────────────────────────────────

    async def create_audit_event(self, timestamp: str, action: str, actor: str,
                                  resource: Optional[str], detail: str,
                                  status: str, ip_address: Optional[str]) -> None:
        await self._execute(
            "INSERT INTO audit_events (timestamp, action, actor, resource, detail, status, ip_address) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (timestamp, action, actor, resource, detail, status, ip_address),
        )

    async def get_audit_events(self, limit: int = 100, offset: int = 0,
                                action_filter: Optional[str] = None,
                                actor_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        conditions = ["1=1"]
        params: list = []
        if action_filter:
            conditions.append("action LIKE ?")
            params.append(f"%{action_filter}%")
        if actor_filter:
            conditions.append("actor LIKE ?")
            params.append(f"%{actor_filter}%")
        where = " AND ".join(conditions)
        return await self._fetchall(
            f"SELECT * FROM audit_events WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )

    async def count_audit_events(self) -> int:
        row = await self._fetchone("SELECT COUNT(*) as cnt FROM audit_events")
        return row["cnt"] if row else 0

    async def export_audit_events(self) -> List[Dict[str, Any]]:
        return await self._fetchall("SELECT * FROM audit_events ORDER BY id ASC")

    # ── Webhook operations ──────────────────────────────────────────────

    async def create_webhook(self, wh_id: str, url: str, events: list,
                              secret: Optional[str]) -> None:
        await self._execute(
            "INSERT INTO webhooks (id, url, events, secret, created_at) VALUES (?, ?, ?, ?, ?)",
            (wh_id, url, json.dumps(events), secret, datetime.now(timezone.utc).isoformat()),
        )

    async def get_webhook(self, wh_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM webhooks WHERE id = ?", (wh_id,))

    async def list_webhooks(self) -> List[Dict[str, Any]]:
        return await self._fetchall("SELECT * FROM webhooks ORDER BY created_at DESC")

    async def delete_webhook(self, wh_id: str) -> bool:
        c = await self._execute("DELETE FROM webhooks WHERE id = ?", (wh_id,))
        return c > 0

    # ── Hypothesis operations ────────────────────────────────────────────

    async def save_hypothesis(self, hypothesis_id: str, hypothesis_text: str,
                               confidence: float, supporting_evidence: list,
                               evidence_items: list,
                               suggested_experiments: list,
                               related_concepts: list,
                               source_category: Optional[str],
                               evaluated: bool,
                               evaluation_summary: Optional[str]) -> None:
        await self._execute("""
            INSERT INTO hypotheses (id, hypothesis_text, confidence, supporting_evidence,
                                     evidence_items, suggested_experiments, related_concepts,
                                     source_category, evaluated, evaluation_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                evaluated=excluded.evaluated,
                evaluation_summary=excluded.evaluation_summary
        """, (
            hypothesis_id, hypothesis_text, confidence,
            json.dumps(supporting_evidence), json.dumps(evidence_items),
            json.dumps(suggested_experiments), json.dumps(related_concepts),
            source_category, 1 if evaluated else 0, evaluation_summary,
            datetime.now(timezone.utc).isoformat(),
        ))

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchone("SELECT * FROM hypotheses WHERE id = ?", (hypothesis_id,))

    async def list_hypotheses(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM hypotheses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
