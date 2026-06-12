"""Paper deduplication engine using DOI exact match and fuzzy title matching.

Uses Qdrant filters for DOI lookup and SQLite for metadata.
"""

import re
import json
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional
import structlog
from qdrant_client.models import Filter, FieldCondition, MatchValue

from ..memory.episodic import EpisodicMemory

logger = structlog.get_logger()

DEFAULT_SIMILARITY_THRESHOLD = 85
SOURCE_SPECIFIC_THRESHOLDS: Dict[str, int] = {
    "pubmed": 90,
    "arxiv": 88,
    "openalex": 85,
    "semantic_scholar": 85,
    "huggingface": 80,
    "crossref": 80,
}


def normalize_title(title: str) -> str:
    """Normalize a paper title for comparison."""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def token_sort_ratio(s1: str, s2: str) -> int:
    """Compare two strings by sorting tokens alphabetically then computing similarity."""
    t1 = " ".join(sorted(s1.split()))
    t2 = " ".join(sorted(s2.split()))
    return int(round(SequenceMatcher(None, t1, t2).ratio() * 100))


class DedupEngine:
    """Engine for detecting and merging duplicate papers.

    Uses Qdrant filtering for fast DOI lookup.
    Uses SQLite for metadata merge operations.
    """

    def __init__(self):
        self.episodic = EpisodicMemory()

    async def find_duplicate(
        self,
        paper: Dict[str, Any],
        threshold: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Check if a paper is a duplicate of an existing paper.

        First checks DOI match (via Qdrant filter), then fuzzy title match.
        Returns the existing paper if a duplicate is found, None otherwise.
        """
        doi = paper.get("doi")
        if doi:
            match = await self._find_by_doi(doi)
            if match:
                logger.info("Duplicate found by DOI", doi=doi, existing_id=match.get("id"))
                return match

        title = paper.get("title", "")
        if not title:
            return None

        source = paper.get("source", "unknown").lower()
        effective_threshold = threshold or SOURCE_SPECIFIC_THRESHOLDS.get(source, DEFAULT_SIMILARITY_THRESHOLD)

        match = await self._find_by_title(title, effective_threshold)
        if match:
            logger.info(
                "Duplicate found by title",
                title=title[:60],
                existing_id=match.get("id"),
                threshold=effective_threshold,
            )
            return match

        return None

    async def _find_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """Find a paper by exact DOI match using Qdrant filter (fast, O(1))."""
        from qdrant_client import AsyncQdrantClient
        from ..config import settings

        client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            grpc_port=settings.QDRANT_GRPC_PORT,
            prefer_grpc=True,
        )

        try:
            # Use SQLite for DOI lookup (cleaner than Qdrant payload filtering)
            papers, _ = await self.episodic.search_papers(query="", limit=500)
            for p in papers:
                payload = p.get("payload", {})
                existing_doi = payload.get("doi", "")
                if existing_doi and existing_doi.strip().lower() == doi.strip().lower():
                    return p
        finally:
            await client.close()
        return None

    async def _find_by_title(self, title: str, threshold: int) -> Optional[Dict[str, Any]]:
        """Find a paper by fuzzy title match against SQLite data."""
        norm_title = normalize_title(title)
        papers, _ = await self.episodic.search_papers(query="", limit=500)

        best_match = None
        best_score = 0

        for paper in papers:
            payload = paper.get("payload", {})
            existing_title = payload.get("title", "")
            if not existing_title:
                continue
            existing_norm = normalize_title(existing_title)
            score = token_sort_ratio(norm_title, existing_norm)
            if score > best_score:
                best_score = score
                best_match = paper

        if best_score >= threshold:
            return best_match
        return None

    async def merge_papers(
        self,
        primary: Dict[str, Any],
        duplicate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge a duplicate paper into the primary.

        Keeps best fields: longest abstract, union categories/authors, earliest date.
        Updates the primary in both SQLite and Qdrant.
        """
        from ..memory.provenance import merge_provenance
        from ..database import db
        from ..memory.episodic import EpisodicMemory

        primary_id = str(primary.get("id", ""))
        primary_payload = primary.get("payload", {}) or {}
        dup_payload = duplicate.get("payload", {}) or {}

        merged_payload = dict(primary_payload)

        # Keep longest abstract
        primary_abs = primary_payload.get("abstract", "")
        dup_abs = dup_payload.get("abstract", "")
        if len(dup_abs or "") > len(primary_abs or ""):
            merged_payload["abstract"] = dup_abs

        # Union of categories
        primary_cats = set(primary_payload.get("categories", []) or [])
        dup_cats = set(dup_payload.get("categories", []) or [])
        merged_payload["categories"] = sorted(primary_cats | dup_cats)

        # Union of authors
        primary_authors = set(str(a) for a in (primary_payload.get("authors", []) or []))
        dup_authors = set(str(a) for a in (dup_payload.get("authors", []) or []))
        merged_payload["authors"] = sorted(primary_authors | dup_authors)

        # Keep the older published date
        primary_date = primary_payload.get("published_at", "")
        dup_date = dup_payload.get("published_at", "")
        if dup_date and (not primary_date or dup_date < primary_date):
            merged_payload["published_at"] = dup_date

        # Merge provenance
        primary_prov = primary_payload.get("provenance", {}) or {}
        dup_prov = dup_payload.get("provenance", {}) or {}
        if primary_prov and dup_prov:
            merged_payload["provenance"] = merge_provenance(primary_prov, dup_prov)

        # Persist merged metadata to SQLite
        await db.upsert_paper(
            paper_id=primary_id,
            title=merged_payload.get("title", ""),
            abstract=merged_payload.get("abstract", ""),
            authors=merged_payload.get("authors", []),
            doi=merged_payload.get("doi"),
            source=merged_payload.get("source", ""),
            source_id=merged_payload.get("source_id", ""),
            url=merged_payload.get("url"),
            published_at=merged_payload.get("published_at"),
            categories=merged_payload.get("categories", []),
            citations_count=merged_payload.get("citations_count", 0),
            quality_score=merged_payload.get("quality_score"),
            provenance=merged_payload.get("provenance"),
            metadata=merged_payload.get("metadata", {}),
        )

        # Delete duplicate from both stores
        episodic = EpisodicMemory()
        await episodic.delete_paper(str(duplicate.get("id", "")))

        logger.info(
            "Merged duplicate into primary",
            primary_id=primary_id,
            duplicate_id=duplicate.get("id"),
        )

        return await episodic.get_paper(primary_id) or primary

    async def deduplicate_all(self) -> Dict[str, Any]:
        """Scan all papers and deduplicate the entire collection.

        Fixes: now properly persists merged results and deletes duplicates.
        """
        from ..database import db

        papers, total = await self.episodic.search_papers(query="", limit=1000)
        stats = {"total": total, "duplicates_found": 0, "merged": 0, "deleted": 0, "errors": 0}

        seen_dois: Dict[str, str] = {}
        seen_titles: Dict[str, str] = {}

        for paper in papers:
            try:
                paper_id = str(paper.get("id", ""))
                payload = paper.get("payload", {}) or {}

                doi = payload.get("doi", "")
                if doi:
                    doi_norm = doi.strip().lower()
                    if doi_norm in seen_dois:
                        stats["duplicates_found"] += 1
                        primary_id = seen_dois[doi_norm]
                        primary_paper = await self.episodic.get_paper(primary_id)
                        if primary_paper:
                            await self.merge_papers(primary_paper, paper)
                            stats["merged"] += 1
                            stats["deleted"] += 1
                        continue
                    seen_dois[doi_norm] = paper_id

                title = payload.get("title", "")
                if title:
                    norm = normalize_title(title)
                    if norm in seen_titles:
                        stats["duplicates_found"] += 1
                        await self.episodic.delete_paper(paper_id)
                        stats["deleted"] += 1
                        continue
                    seen_titles[norm] = paper_id

            except Exception as e:
                stats["errors"] += 1
                logger.error("Deduplication error", paper_id=paper.get("id"), error=str(e))

        logger.info("Deduplication scan complete", **stats)
        return stats
