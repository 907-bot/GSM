"""
Citation Agent — fetches and stores citation graphs using Semantic Scholar API.

For any indexed paper, this agent:
1. Fetches references (papers it cites) and citations (papers that cite it)
2. Stores CITES relationships in Neo4j
3. Indexes referenced papers into Qdrant for discovery
"""

from typing import List, Dict, Any, Optional
import httpx
import structlog
from ..config import settings
from ..memory.graph_schema import graph_schema
from ..bus import event_bus
from ..events import EventType, Event

logger = structlog.get_logger()

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"


class CitationAgent:
    """
    Fetches and indexes citation graphs via the free Semantic Scholar API.
    Stores CITES relationships in Neo4j.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SEMANTIC_SCHOLAR_API_KEY

    def _headers(self) -> Dict[str, str]:
        h = {}
        if self.api_key:
            h["x-api-key"] = self.api_key
        return h

    async def fetch_citations(
        self,
        paper_id: str,
        doi: Optional[str] = None,
        semantic_id: Optional[str] = None,
        limit: int = 50,
        direction: str = "both",  # "references", "citations", or "both"
    ) -> Dict[str, Any]:
        """
        Fetch references and/or citations for a paper.
        Returns dict with "references" and "citations" lists.
        """
        # Resolve Semantic Scholar paper ID
        ss_id = semantic_id or await self._resolve_paper_id(paper_id, doi)
        if not ss_id:
            return {"references": [], "citations": [], "paper_id": paper_id}

        result: Dict[str, Any] = {
            "paper_id": paper_id,
            "semantic_scholar_id": ss_id,
            "references": [],
            "citations": [],
        }

        if direction in ("references", "both"):
            result["references"] = await self._fetch_references(ss_id, limit)

        if direction in ("citations", "both"):
            result["citations"] = await self._fetch_citing_papers(ss_id, limit)

        # Store CITES relationships in Neo4j
        await self._store_citation_graph(paper_id, result)

        await event_bus.publish(Event(
            type=EventType.PAPER_INDEXED,
            data={
                "paper_id": paper_id,
                "references_found": len(result["references"]),
                "citations_found": len(result["citations"]),
                "event": "citation_graph_built",
            },
            room="pipeline",
        ))

        logger.info(
            "Citation graph built",
            paper_id=paper_id,
            references=len(result["references"]),
            citations=len(result["citations"]),
        )
        return result

    async def _resolve_paper_id(
        self, internal_id: str, doi: Optional[str]
    ) -> Optional[str]:
        """Resolve internal paper ID or DOI to Semantic Scholar paper ID."""
        if doi:
            async with httpx.AsyncClient(timeout=20.0) as client:
                try:
                    resp = await client.get(
                        f"{SEMANTIC_SCHOLAR_BASE}/paper/DOI:{doi}",
                        params={"fields": "paperId"},
                        headers=self._headers(),
                    )
                    if resp.status_code == 200:
                        return resp.json().get("paperId")
                except Exception as e:
                    logger.warning("DOI resolution failed", doi=doi, error=str(e))
        return None

    async def _fetch_references(
        self, ss_paper_id: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch papers that this paper references."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{SEMANTIC_SCHOLAR_BASE}/paper/{ss_paper_id}/references",
                    params={
                        "fields": "paperId,title,abstract,authors,year,externalIds,citationCount",
                        "limit": limit,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [self._parse_ss_paper(item.get("citedPaper", {}))
                        for item in data.get("data", [])
                        if item.get("citedPaper")]
            except Exception as e:
                logger.warning("Fetch references failed", ss_id=ss_paper_id, error=str(e))
                return []

    async def _fetch_citing_papers(
        self, ss_paper_id: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch papers that cite this paper."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{SEMANTIC_SCHOLAR_BASE}/paper/{ss_paper_id}/citations",
                    params={
                        "fields": "paperId,title,abstract,authors,year,externalIds,citationCount",
                        "limit": limit,
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [self._parse_ss_paper(item.get("citingPaper", {}))
                        for item in data.get("data", [])
                        if item.get("citingPaper")]
            except Exception as e:
                logger.warning("Fetch citations failed", ss_id=ss_paper_id, error=str(e))
                return []

    def _parse_ss_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "semantic_scholar_id": paper.get("paperId", ""),
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": [a.get("name", "") for a in paper.get("authors", [])],
            "year": paper.get("year"),
            "doi": (paper.get("externalIds") or {}).get("DOI"),
            "citations_count": paper.get("citationCount", 0),
        }

    async def _store_citation_graph(
        self, paper_id: str, citation_data: Dict[str, Any]
    ) -> None:
        """Store CITES relationships in Neo4j."""
        # Paper cites its references
        for ref in citation_data.get("references", []):
            ref_id = ref.get("semantic_scholar_id") or ref.get("doi", "")
            if not ref_id:
                continue
            await graph_schema.upsert_paper_full(
                paper_id=ref_id,
                title=ref.get("title", ""),
                doi=ref.get("doi"),
                authors=ref.get("authors", []),
                published_at=str(ref.get("year", "")),
                citations_count=ref.get("citations_count", 0),
            )
            await graph_schema.add_relation(
                source_id=paper_id,
                source_label="Paper",
                target_id=ref_id,
                target_label="Paper",
                relation_type="CITES",
            )

        # Citing papers cite this paper
        for cit in citation_data.get("citations", []):
            cit_id = cit.get("semantic_scholar_id") or cit.get("doi", "")
            if not cit_id:
                continue
            await graph_schema.upsert_paper_full(
                paper_id=cit_id,
                title=cit.get("title", ""),
                doi=cit.get("doi"),
                authors=cit.get("authors", []),
                published_at=str(cit.get("year", "")),
                citations_count=cit.get("citations_count", 0),
            )
            await graph_schema.add_relation(
                source_id=cit_id,
                source_label="Paper",
                target_id=paper_id,
                target_label="Paper",
                relation_type="CITES",
            )

    async def build_citation_graph_for_collection(
        self,
        paper_ids: List[str],
        dois: Optional[List[str]] = None,
        limit_per_paper: int = 30,
    ) -> Dict[str, Any]:
        """Build citation graph for a batch of papers."""
        total_refs = 0
        total_cits = 0
        failed = 0

        for i, paper_id in enumerate(paper_ids):
            doi = dois[i] if dois and i < len(dois) else None
            try:
                result = await self.fetch_citations(
                    paper_id=paper_id,
                    doi=doi,
                    limit=limit_per_paper,
                )
                total_refs += len(result["references"])
                total_cits += len(result["citations"])
            except Exception as e:
                failed += 1
                logger.error("Citation fetch failed for paper", paper_id=paper_id, error=str(e))

        return {
            "papers_processed": len(paper_ids),
            "failed": failed,
            "total_references_stored": total_refs,
            "total_citations_stored": total_cits,
        }


# Singleton
citation_agent = CitationAgent()
