"""
Extended paper sources: bioRxiv, medRxiv, CORE Open Access.

All free:
  - bioRxiv / medRxiv: https://api.biorxiv.org  (no key required)
  - CORE: https://core.ac.uk/api-documentation  (free key: register email)
"""

import httpx
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class BioRxivSource:
    """bioRxiv REST API — biology & life sciences preprints. No API key needed."""

    BASE_URL = "https://api.biorxiv.org/details/biorxiv"

    async def search(
        self,
        query: str,
        max_results: int = 50,
        interval: str = "2024-01-01/2026-12-31",
    ) -> List[Dict[str, Any]]:
        """
        bioRxiv doesn't have a keyword search endpoint — it returns papers in a
        date range. We fetch recent papers and filter client-side.
        """
        url = f"{self.BASE_URL}/{interval}/0/{max_results}/json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                all_papers = self._parse_response(data)
                # Client-side keyword filter
                q_lower = query.lower()
                return [
                    p for p in all_papers
                    if q_lower in (p.get("title") or "").lower()
                    or q_lower in (p.get("abstract") or "").lower()
                ]
            except Exception as e:
                logger.error("bioRxiv search failed", error=str(e))
                return []

    async def fetch_latest(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fetch the latest bioRxiv papers."""
        from datetime import datetime, timedelta
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        interval = f"{week_ago.strftime('%Y-%m-%d')}/{today.strftime('%Y-%m-%d')}"
        url = f"{self.BASE_URL}/{interval}/0/{max_results}/json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return self._parse_response(resp.json())
            except Exception as e:
                logger.error("bioRxiv fetch_latest failed", error=str(e))
                return []

    def _parse_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        papers = []
        collection = data.get("collection", [])
        for item in collection:
            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "authors": [a.strip() for a in item.get("authors", "").split(";") if a.strip()],
                "source": "biorxiv",
                "source_id": item.get("doi", ""),
                "doi": item.get("doi"),
                "url": f"https://www.biorxiv.org/content/{item.get('doi')}",
                "published_at": item.get("date", ""),
                "categories": [item.get("category", "")],
                "citations_count": 0,
                "metadata": {
                    "version": item.get("version", "1"),
                    "type": item.get("type", "new_result"),
                    "server": "biorxiv",
                },
            })
        return papers


class MedRxivSource:
    """medRxiv REST API — clinical medicine preprints. No API key needed."""

    BASE_URL = "https://api.biorxiv.org/details/medrxiv"

    async def search(
        self,
        query: str,
        max_results: int = 50,
        interval: str = "2024-01-01/2026-12-31",
    ) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/{interval}/0/{max_results}/json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                all_papers = self._parse_response(data)
                q_lower = query.lower()
                return [
                    p for p in all_papers
                    if q_lower in (p.get("title") or "").lower()
                    or q_lower in (p.get("abstract") or "").lower()
                ]
            except Exception as e:
                logger.error("medRxiv search failed", error=str(e))
                return []

    def _parse_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        papers = []
        for item in data.get("collection", []):
            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "authors": [a.strip() for a in item.get("authors", "").split(";") if a.strip()],
                "source": "medrxiv",
                "source_id": item.get("doi", ""),
                "doi": item.get("doi"),
                "url": f"https://www.medrxiv.org/content/{item.get('doi')}",
                "published_at": item.get("date", ""),
                "categories": [item.get("category", "")],
                "citations_count": 0,
                "metadata": {"server": "medrxiv"},
            })
        return papers


class CORESource:
    """
    CORE Open Access API v3.
    Free key: register at https://core.ac.uk/api-documentation
    Without a key, rate limit is very low — a key is strongly recommended.
    """

    BASE_URL = "https://api.core.ac.uk/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/search/works",
                    json={
                        "q": query,
                        "limit": limit,
                        "offset": offset,
                        "filters": {"exists": ["abstract"]},
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_results(data.get("results", []))
            except Exception as e:
                logger.error("CORE search failed", error=str(e))
                return []

    def _parse_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        papers = []
        for item in results:
            authors = []
            for a in item.get("authors", []):
                name = a.get("name", "")
                if name:
                    authors.append(name)

            papers.append({
                "title": item.get("title", ""),
                "abstract": item.get("abstract", ""),
                "authors": authors,
                "source": "core",
                "source_id": str(item.get("id", "")),
                "doi": item.get("doi"),
                "url": item.get("sourceFulltextUrls", [None])[0] or item.get("downloadUrl"),
                "published_at": item.get("publishedDate", item.get("yearPublished", "")),
                "citations_count": item.get("citationCount", 0),
                "categories": item.get("subjects", []),
                "metadata": {
                    "publisher": item.get("publisher"),
                    "journal": item.get("journals", [{}])[0].get("title") if item.get("journals") else None,
                    "fulltext_available": bool(item.get("fullText")),
                    "source": "core_open_access",
                },
            })
        return papers
