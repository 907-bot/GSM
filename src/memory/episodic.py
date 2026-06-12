"""Qdrant-based vector memory for semantic search.

Qdrant stores only vectors + paper_id references.
All paper metadata lives in SQLite (see src/database.py).
"""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
from ..config import settings
from ..database import db
import structlog

logger = structlog.get_logger()


class EpisodicMemory:
    """Qdrant-based episodic memory for vector search of papers and findings.

    Qdrant stores: {id, vector, payload: {type, paper_id}}
    SQLite stores: all paper metadata
    """

    def __init__(self):
        self.client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            prefer_grpc=True,
        )
        self.collection = settings.QDRANT_COLLECTION

    async def ensure_collection(self) -> None:
        try:
            collections = await self.client.get_collections()
            if not any(c.name == self.collection for c in collections.collections):
                await self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=384,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection", collection=self.collection)
        except Exception as e:
            logger.error("Failed to ensure collection", error=str(e))

    async def store_paper(self, paper_data: Dict[str, Any], embedding: np.ndarray) -> str:
        """Store a paper vector in Qdrant. Metadata goes to SQLite."""
        point_id = str(paper_data["id"])

        await self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={
                        "type": "paper",
                        "paper_id": point_id,
                    },
                )
            ],
        )

        await db.upsert_paper(
            paper_id=point_id,
            title=paper_data.get("title", ""),
            abstract=paper_data.get("abstract", ""),
            authors=paper_data.get("authors", []),
            doi=paper_data.get("doi"),
            source=paper_data.get("source", ""),
            source_id=paper_data.get("source_id", ""),
            url=paper_data.get("url"),
            published_at=paper_data.get("published_at"),
            categories=paper_data.get("categories", []),
            citations_count=paper_data.get("citations_count", 0),
            quality_score=paper_data.get("quality_score"),
            provenance=paper_data.get("provenance"),
            metadata=paper_data.get("metadata", {}),
        )

        logger.info("Stored paper", paper_id=point_id)
        return point_id

    async def store_finding(self, finding_data: Dict[str, Any], embedding: np.ndarray) -> str:
        """Store a finding vector in Qdrant."""
        point_id = str(finding_data["id"])
        await self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload={
                        "type": "finding",
                        "paper_id": str(finding_data.get("paper_id", "")),
                        "finding_text": finding_data.get("finding_text", ""),
                        "confidence": finding_data.get("confidence", 0.0),
                        "entities": finding_data.get("entities", []),
                        "relationships": finding_data.get("relationships", []),
                    },
                )
            ],
        )
        logger.info("Stored finding in episodic memory", finding_id=point_id)
        return point_id

    async def search_similar(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        filter_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar items in memory by vector similarity.

        Returns results with paper_id; caller fetches metadata from SQLite.
        """
        search_filter = None
        if filter_type:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="type",
                        match=MatchValue(value=filter_type),
                    )
                ]
            )

        results = await self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding.tolist(),
            limit=limit,
            query_filter=search_filter,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

    async def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Get a paper's metadata from SQLite."""
        row = await db.get_paper(paper_id)
        if not row:
            return None
        return {
            "id": row["id"],
            "payload": self._row_to_payload(row),
        }

    async def count_papers(self) -> int:
        return await db.count_papers()

    async def list_papers(self, limit: int = 50, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """List papers from SQLite with pagination."""
        papers, _ = await db.search_papers(limit=limit, offset=offset or 0)
        return papers

    async def search_papers(
        self,
        query: str = "",
        source: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        quality_min: Optional[float] = None,
        author: Optional[str] = None,
        sort_by: str = "published_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search papers with text query and filters via SQLite full-text search."""
        return await db.search_papers(
            query=query,
            source=source,
            category=category,
            date_from=date_from,
            date_to=date_to,
            quality_min=quality_min,
            author=author,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset or 0,
        )

    async def update_paper(self, paper_id: str, payload: Dict[str, Any]) -> bool:
        """Update paper metadata in SQLite."""
        fields = {
            "title": payload.get("title"),
            "abstract": payload.get("abstract"),
            "authors": payload.get("authors"),
            "doi": payload.get("doi"),
            "source": payload.get("source"),
            "source_id": payload.get("source_id"),
            "url": payload.get("url"),
            "published_at": payload.get("published_at"),
            "categories": payload.get("categories"),
            "citations_count": payload.get("citations_count"),
            "quality_score": payload.get("quality_score"),
            "provenance": payload.get("provenance"),
            "metadata": payload.get("metadata"),
        }
        # Re-upsert via SQLite
        existing = await db.get_paper(paper_id)
        if not existing:
            return False
        merged = {**existing, **{k: v for k, v in fields.items() if v is not None}}
        await db.upsert_paper(
            paper_id=paper_id,
            title=merged.get("title", ""),
            abstract=merged.get("abstract", ""),
            authors=merged.get("authors", []),
            doi=merged.get("doi"),
            source=merged.get("source", ""),
            source_id=merged.get("source_id", ""),
            url=merged.get("url"),
            published_at=merged.get("published_at"),
            categories=merged.get("categories", []),
            citations_count=merged.get("citations_count", 0),
            quality_score=merged.get("quality_score"),
            provenance=merged.get("provenance"),
            metadata=merged.get("metadata", {}),
        )
        return True

    async def archive_paper(self, paper_id: str) -> bool:
        return await db.archive_paper(paper_id)

    async def delete_paper(self, paper_id: str) -> bool:
        """Delete paper from both Qdrant and SQLite."""
        try:
            await self.client.delete(
                collection_name=self.collection,
                points_selector=[paper_id],
            )
        except Exception:
            pass
        return await db.delete_paper(paper_id)

    async def get_recent_papers(self, limit: int = 100) -> List[Dict[str, Any]]:
        papers, _ = await db.search_papers(sort_by="indexed_at", sort_order="desc", limit=limit)
        return papers

    async def get_papers_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        rows = await db.get_papers_by_ids(ids)
        return [{"id": r["id"], "payload": self._row_to_payload(r)} for r in rows]

    def _row_to_payload(self, row: dict) -> dict:
        import json
        return {
            "type": "paper",
            "title": row.get("title", ""),
            "abstract": row.get("abstract", ""),
            "authors": json.loads(row["authors"]) if isinstance(row.get("authors"), str) else (row.get("authors") or []),
            "doi": row.get("doi"),
            "source": row.get("source", ""),
            "source_id": row.get("source_id", ""),
            "url": row.get("url"),
            "published_at": row.get("published_at"),
            "categories": json.loads(row["categories"]) if isinstance(row.get("categories"), str) else (row.get("categories") or []),
            "citations_count": row.get("citations_count", 0),
            "quality_score": row.get("quality_score"),
            "provenance": json.loads(row["provenance"]) if row.get("provenance") else None,
            "metadata": json.loads(row["metadata"]) if row.get("metadata") else {},
            "archived": bool(row.get("archived", 0)),
            "archived_at": row.get("archived_at"),
        }
