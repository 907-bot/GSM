"""PostgreSQL backend using asyncpg — production-grade connection pooling.

Used when DATABASE_URL starts with postgresql:// or postgres://.
Falls back to SQLite otherwise.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import asyncpg
import structlog

from .database_backend import DatabaseBackend

logger = structlog.get_logger()

POOL_MIN_SIZE = 2
POOL_MAX_SIZE = 10
COMMAND_TIMEOUT = 30


class PostgresBackend(DatabaseBackend):
    """PostgreSQL implementation of DatabaseBackend using asyncpg connection pool."""

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            command_timeout=COMMAND_TIMEOUT,
        )
        await self._migrate()
        logger.info("PostgresBackend connected", dsn=self._dsn.split("@")[-1] if "@" in self._dsn else "configured")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def _migrate(self) -> None:
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT DEFAULT '',
                    role TEXT DEFAULT 'viewer',
                    api_key TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_login TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

                CREATE TABLE IF NOT EXISTS papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT DEFAULT '',
                    authors JSONB DEFAULT '[]',
                    doi TEXT,
                    source TEXT DEFAULT 'unknown',
                    source_id TEXT DEFAULT '',
                    url TEXT,
                    published_at TIMESTAMPTZ,
                    categories JSONB DEFAULT '[]',
                    citations_count INTEGER DEFAULT 0,
                    quality_score DOUBLE PRECISION,
                    provenance JSONB,
                    metadata JSONB DEFAULT '{}',
                    archived BOOLEAN DEFAULT FALSE,
                    archived_at TIMESTAMPTZ,
                    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
                CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
                CREATE INDEX IF NOT EXISTS idx_papers_quality ON papers(quality_score);
                CREATE INDEX IF NOT EXISTS idx_papers_archived ON papers(archived);
                CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_at);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    resource TEXT,
                    detail JSONB DEFAULT '{}',
                    status TEXT DEFAULT 'success',
                    ip_address TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);

                CREATE TABLE IF NOT EXISTS webhooks (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    events JSONB NOT NULL DEFAULT '["all"]',
                    secret TEXT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS retention_policies (
                    name TEXT PRIMARY KEY,
                    max_age_days INTEGER,
                    min_quality_score DOUBLE PRECISION,
                    sources_to_keep JSONB,
                    sources_to_purge JSONB,
                    archive_inactive_days INTEGER,
                    action TEXT DEFAULT 'archive'
                );

                CREATE TABLE IF NOT EXISTS hypotheses (
                    id TEXT PRIMARY KEY,
                    hypothesis_text TEXT NOT NULL,
                    confidence DOUBLE PRECISION DEFAULT 0.5,
                    supporting_evidence JSONB DEFAULT '[]',
                    evidence_items JSONB DEFAULT '[]',
                    suggested_experiments JSONB DEFAULT '[]',
                    related_concepts JSONB DEFAULT '[]',
                    source_category TEXT,
                    evaluated BOOLEAN DEFAULT FALSE,
                    evaluation_summary TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_hypotheses_created ON hypotheses(created_at);
                CREATE INDEX IF NOT EXISTS idx_hypotheses_source ON hypotheses(source_category);
            """)

    # ── Generic helpers ─────────────────────────────────────────────────

    async def _exec(self, sql: str, *args) -> str:
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            return await conn.execute(sql, *args)

    async def _fetchrow(self, sql: str, *args) -> Optional[Dict[str, Any]]:
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def _fetch(self, sql: str, *args) -> List[Dict[str, Any]]:
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    # ── User operations ─────────────────────────────────────────────────

    async def create_user(self, user_id: str, email: str, password_hash: str,
                           name: str, role: str, api_key: str) -> bool:
        try:
            await self._exec(
                "INSERT INTO users (id, email, password_hash, name, role, api_key) VALUES ($1, $2, $3, $4, $5, $6)",
                user_id, email.lower().strip(), password_hash, name, role, api_key,
            )
            return True
        except asyncpg.UniqueViolationError:
            return False

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM users WHERE email = $1", email.lower().strip())

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM users WHERE api_key = $1 AND is_active = TRUE", api_key)

    async def list_users(self) -> List[Dict[str, Any]]:
        return await self._fetch("SELECT * FROM users ORDER BY created_at DESC")

    async def update_user_login(self, user_id: str) -> None:
        await self._exec("UPDATE users SET last_login = NOW() WHERE id = $1", user_id)

    async def update_user_role(self, email: str, role: str) -> bool:
        r = await self._exec("UPDATE users SET role = $1 WHERE email = $2", role, email.lower().strip())
        return "UPDATE 1" in r

    async def deactivate_user(self, email: str) -> bool:
        r = await self._exec("UPDATE users SET is_active = FALSE WHERE email = $1", email.lower().strip())
        return "UPDATE 1" in r

    # ── Paper operations ────────────────────────────────────────────────

    async def upsert_paper(self, paper_id: str, title: str, abstract: str,
                            authors: list, doi: Optional[str], source: str,
                            source_id: str, url: Optional[str],
                            published_at: Optional[str], categories: list,
                            citations_count: int, quality_score: Optional[float],
                            provenance: Optional[dict], metadata: dict) -> None:
        await self._exec("""
            INSERT INTO papers (id, title, abstract, authors, doi, source, source_id, url,
                                published_at, categories, citations_count, quality_score,
                                provenance, metadata, indexed_at)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9::timestamptz,
                    $10::jsonb, $11, $12, $13::jsonb, $14::jsonb, NOW())
            ON CONFLICT (id) DO UPDATE SET
                title=EXCLUDED.title, abstract=EXCLUDED.abstract, authors=EXCLUDED.authors,
                doi=EXCLUDED.doi, source=EXCLUDED.source, source_id=EXCLUDED.source_id,
                url=EXCLUDED.url, published_at=EXCLUDED.published_at,
                categories=EXCLUDED.categories, citations_count=EXCLUDED.citations_count,
                quality_score=EXCLUDED.quality_score, provenance=EXCLUDED.provenance,
                metadata=EXCLUDED.metadata
        """,
            paper_id, title, abstract, json.dumps(authors), doi, source, source_id, url,
            published_at, json.dumps(categories), citations_count, quality_score,
            json.dumps(provenance) if provenance else None,
            json.dumps(metadata) if metadata else "{}",
        )

    async def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM papers WHERE id = $1", paper_id)

    async def search_papers(self, query: str = "", source: Optional[str] = None,
                             category: Optional[str] = None,
                             date_from: Optional[str] = None,
                             date_to: Optional[str] = None,
                             quality_min: Optional[float] = None,
                             author: Optional[str] = None,
                             sort_by: str = "published_at",
                             sort_order: str = "desc", limit: int = 50,
                             offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        conditions = ["archived = FALSE"]
        params: list = []
        idx = 1

        if query:
            conditions.append(f"(title ILIKE ${idx} OR abstract ILIKE ${idx})")
            params.append(f"%{query}%")
            idx += 1

        if source:
            conditions.append(f"source = ${idx}")
            params.append(source.lower())
            idx += 1

        if category:
            conditions.append(f"categories::text ILIKE ${idx}")
            params.append(f"%{category}%")
            idx += 1

        if date_from:
            conditions.append(f"published_at >= ${idx}::timestamptz")
            params.append(date_from)
            idx += 1

        if date_to:
            conditions.append(f"published_at <= ${idx}::timestamptz")
            params.append(date_to)
            idx += 1

        if quality_min is not None:
            conditions.append(f"quality_score >= ${idx}")
            params.append(quality_min)
            idx += 1

        if author:
            conditions.append(f"authors::text ILIKE ${idx}")
            params.append(f"%{author}%")
            idx += 1

        where = " AND ".join(conditions)
        valid_sort = {"published_at", "quality_score", "title", "citations_count", "indexed_at"}
        sort_col = sort_by if sort_by in valid_sort else "published_at"
        order = "DESC" if sort_order == "desc" else "ASC"

        count_sql = f"SELECT COUNT(*) as cnt FROM papers WHERE {where}"
        row = await self._fetchrow(count_sql, *params)
        total = row["cnt"] if row else 0

        params.extend([limit, offset])
        data_sql = f"SELECT * FROM papers WHERE {where} ORDER BY {sort_col} {order} LIMIT ${idx} OFFSET ${idx + 1}"

        rows = await self._fetch(data_sql, *params)
        papers = [{"id": r["id"], "payload": self._paper_payload(r)} for r in rows]
        return papers, total

    def _paper_payload(self, r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "paper",
            "title": r["title"],
            "abstract": r.get("abstract", ""),
            "authors": r.get("authors", []),
            "doi": r.get("doi"),
            "source": r.get("source"),
            "source_id": r.get("source_id"),
            "url": r.get("url"),
            "published_at": str(r["published_at"]) if r.get("published_at") else None,
            "categories": r.get("categories", []),
            "citations_count": r.get("citations_count", 0),
            "quality_score": r.get("quality_score"),
            "provenance": r.get("provenance"),
            "metadata": r.get("metadata", {}),
            "archived": r.get("archived", False),
            "archived_at": str(r["archived_at"]) if r.get("archived_at") else None,
        }

    async def count_papers(self) -> int:
        row = await self._fetchrow("SELECT COUNT(*) as cnt FROM papers WHERE archived = FALSE")
        return row["cnt"] if row else 0

    async def archive_paper(self, paper_id: str) -> bool:
        r = await self._exec(
            "UPDATE papers SET archived = TRUE, archived_at = NOW() WHERE id = $1", paper_id
        )
        return "UPDATE 1" in r

    async def delete_paper(self, paper_id: str) -> bool:
        r = await self._exec("DELETE FROM papers WHERE id = $1", paper_id)
        return "DELETE 1" in r

    async def get_papers_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        rows = await self._fetch(
            "SELECT * FROM papers WHERE id = ANY($1::text[])", ids
        )
        return rows

    async def unarchive_paper(self, paper_id: str) -> bool:
        r = await self._exec(
            "UPDATE papers SET archived = FALSE, archived_at = NULL WHERE id = $1", paper_id
        )
        return "UPDATE 1" in r

    async def get_papers_for_retention(self, limit: int = 1000) -> List[Dict[str, Any]]:
        return await self._fetch(
            "SELECT * FROM papers WHERE archived = FALSE ORDER BY published_at ASC LIMIT $1", limit
        )

    async def get_archived_papers(self) -> List[Dict[str, Any]]:
        return await self._fetch(
            "SELECT id, title, archived_at FROM papers WHERE archived = TRUE ORDER BY archived_at DESC"
        )

    # ── Audit operations ────────────────────────────────────────────────

    async def create_audit_event(self, timestamp: str, action: str, actor: str,
                                  resource: Optional[str], detail: str,
                                  status: str, ip_address: Optional[str]) -> None:
        await self._exec(
            "INSERT INTO audit_events (timestamp, action, actor, resource, detail, status, ip_address) "
            "VALUES ($1::timestamptz, $2, $3, $4, $5::jsonb, $6, $7)",
            timestamp, action, actor, resource, detail, status, ip_address,
        )

    async def get_audit_events(self, limit: int = 100, offset: int = 0,
                                action_filter: Optional[str] = None,
                                actor_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        conditions: list = []
        params: list = []
        idx = 1
        if action_filter:
            conditions.append(f"action ILIKE ${idx}")
            params.append(f"%{action_filter}%")
            idx += 1
        if actor_filter:
            conditions.append(f"actor ILIKE ${idx}")
            params.append(f"%{actor_filter}%")
            idx += 1
        where = " AND ".join(conditions) if conditions else "TRUE"
        params.extend([limit, offset])
        return await self._fetch(
            f"SELECT * FROM audit_events WHERE {where} ORDER BY id DESC LIMIT ${idx} OFFSET ${idx + 1}",
            *params,
        )

    async def count_audit_events(self) -> int:
        row = await self._fetchrow("SELECT COUNT(*) as cnt FROM audit_events")
        return row["cnt"] if row else 0

    async def export_audit_events(self) -> List[Dict[str, Any]]:
        return await self._fetch("SELECT * FROM audit_events ORDER BY id ASC")

    # ── Webhook operations ──────────────────────────────────────────────

    async def create_webhook(self, wh_id: str, url: str, events: list,
                              secret: Optional[str]) -> None:
        await self._exec(
            "INSERT INTO webhooks (id, url, events, secret) VALUES ($1, $2, $3::jsonb, $4)",
            wh_id, url, json.dumps(events), secret,
        )

    async def get_webhook(self, wh_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM webhooks WHERE id = $1", wh_id)

    async def list_webhooks(self) -> List[Dict[str, Any]]:
        return await self._fetch("SELECT * FROM webhooks ORDER BY created_at DESC")

    async def delete_webhook(self, wh_id: str) -> bool:
        r = await self._exec("DELETE FROM webhooks WHERE id = $1", wh_id)
        return "DELETE 1" in r

    # ── Hypothesis operations ────────────────────────────────────────────

    async def save_hypothesis(self, hypothesis_id: str, hypothesis_text: str,
                               confidence: float, supporting_evidence: list,
                               evidence_items: list,
                               suggested_experiments: list,
                               related_concepts: list,
                               source_category: Optional[str],
                               evaluated: bool,
                               evaluation_summary: Optional[str]) -> None:
        await self._exec("""
            INSERT INTO hypotheses (id, hypothesis_text, confidence, supporting_evidence,
                                     evidence_items, suggested_experiments, related_concepts,
                                     source_category, evaluated, evaluation_summary, created_at)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8, $9, $10, NOW())
            ON CONFLICT (id) DO UPDATE SET
                evaluated=EXCLUDED.evaluated,
                evaluation_summary=EXCLUDED.evaluation_summary
        """,
            hypothesis_id, hypothesis_text, confidence,
            json.dumps(supporting_evidence), json.dumps(evidence_items),
            json.dumps(suggested_experiments), json.dumps(related_concepts),
            source_category, evaluated, evaluation_summary,
        )

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        return await self._fetchrow("SELECT * FROM hypotheses WHERE id = $1", hypothesis_id)

    async def list_hypotheses(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return await self._fetch(
            "SELECT * FROM hypotheses ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
