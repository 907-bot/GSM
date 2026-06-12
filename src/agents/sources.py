import httpx
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class ArxivSource:
    """arXiv API client for fetching papers."""

    BASE_URL = "https://export.arxiv.org/api/query"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        start: int = 0,
        categories: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            params["search_query"] = f"({params['search_query']}) AND ({cat_query})"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()

        return self._parse_response(response.text)

    def _parse_response(self, xml_content: str) -> List[Dict[str, Any]]:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []

        for entry in root.findall("atom:entry", ns):
            paper = {
                "title": entry.find("atom:title", ns).text.strip(),
                "abstract": entry.find("atom:summary", ns).text.strip(),
                "authors": [
                    author.find("atom:name", ns).text
                    for author in entry.findall("atom:author", ns)
                ],
                "source": "arxiv",
                "source_id": entry.find("atom:id", ns).text.split("/abs/")[-1],
                "url": entry.find("atom:id", ns).text,
                "published_at": entry.find("atom:published", ns).text,
                "categories": [
                    cat.get("term")
                    for cat in entry.findall("atom:category", ns)
                ],
            }
            papers.append(paper)

        return papers


class SemanticScholarSource:
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(
        self,
        query: str,
        limit: int = 100,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if fields is None:
            fields = [
                "paperId", "title", "abstract", "authors", "year",
                "citationCount", "referenceCount", "fieldsOfStudy",
            ]

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/paper/search",
                params={"query": query, "limit": limit, "fields": ",".join(fields)},
                headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        return self._parse_papers(data.get("data", []))

    def _parse_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed = []
        for paper in papers:
            parsed.append({
                "title": paper.get("title", ""),
                "abstract": paper.get("abstract", ""),
                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                "source": "semantic_scholar",
                "source_id": paper.get("paperId", ""),
                "doi": paper.get("externalIds", {}).get("DOI"),
                "published_at": str(paper.get("year", "")),
                "citations_count": paper.get("citationCount", 0),
                "categories": paper.get("fieldsOfStudy", []),
            })
        return parsed


class OpenAlexSource:
    """OpenAlex API client. Pass email in api_key for faster rate limits."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(
        self, query: str, per_page: int = 100, page: int = 1
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"search": query, "per_page": per_page, "page": page}
        # OpenAlex API key is passed as a query parameter (not a header)
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/works",
                params=params,
            )
            response.raise_for_status()

        data = response.json()
        return self._parse_works(data.get("results", []))

    def _parse_works(self, works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed = []
        for work in works:
            parsed.append({
                "title": work.get("title", ""),
                "abstract": work.get("abstract", ""),
                "authors": [
                    a.get("author", {}).get("display_name", "")
                    for a in work.get("authorships", [])
                ],
                "source": "openalex",
                "source_id": work.get("id", ""),
                "doi": work.get("doi"),
                "published_at": work.get("publication_date", ""),
                "citations_count": work.get("cited_by_count", 0),
                "categories": [
                    c.get("display_name", "")
                    for c in work.get("concepts", [])
                ],
            })
        return parsed


class PubMedSource:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    async def search(
        self, query: str, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_resp = await client.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            )
            search_resp.raise_for_status()
            ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            detail_resp = await client.get(
                f"{self.BASE_URL}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            )
            detail_resp.raise_for_status()

        data = detail_resp.json().get("result", {})
        return self._parse_papers(data)

    def _parse_papers(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        parsed = []
        for uid, paper in data.items():
            if uid == "uids":
                continue
            parsed.append({
                "title": paper.get("title", ""),
                "abstract": "",
                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                "source": "pubmed",
                "source_id": uid,
                "doi": paper.get("elocationid", ""),
                "published_at": paper.get("pubdate", ""),
                "categories": [],
            })
        return parsed


class HuggingFacePapersSource:
    """Fetch latest research papers from Hugging Face papers feed and datasets."""

    PAPERS_API = "https://huggingface.co/api/papers"
    DATASETS_API = "https://huggingface.co/api/datasets"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(
        self, query: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search HF papers feed."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    self.PAPERS_API,
                    params={"search": query, "limit": max_results},
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_papers(data if isinstance(data, list) else [])
            except Exception as e:
                logger.warning("HF papers API failed, trying datasets", error=str(e))

            # Fallback: search datasets for paper metadata
            try:
                resp = await client.get(
                    self.DATASETS_API,
                    params={"search": query, "sort": "lastModified", "direction": -1, "limit": max_results},
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_datasets(data if isinstance(data, list) else [])
            except Exception as e:
                logger.warning("HF datasets fallback failed", error=str(e))

        return []

    async def fetch_latest(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fetch latest papers from HF papers feed."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    self.PAPERS_API,
                    params={"limit": max_results},
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_papers(data if isinstance(data, list) else [])
            except Exception as e:
                logger.warning("Failed to fetch latest HF papers", error=str(e))
        return []

    def _parse_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed = []
        for paper in papers:
            title = paper.get("title", "")
            if not title:
                continue
            parsed.append({
                "title": title,
                "abstract": paper.get("abstract", paper.get("summary", "")),
                "authors": paper.get("authors", []) if isinstance(paper.get("authors"), list) else [],
                "source": "huggingface",
                "source_id": paper.get("id", paper.get("paperId", "")),
                "doi": paper.get("doi"),
                "url": paper.get("url", f"https://huggingface.co/papers/{paper.get('id', '')}"),
                "published_at": paper.get("publishedAt", paper.get("date", "")),
                "categories": paper.get("keywords", paper.get("tags", [])),
                "citations_count": paper.get("citationCount", 0),
                "metadata": {
                    "upvotes": paper.get("upvotes", 0),
                    "discussion_count": paper.get("discussionCount", 0),
                    "source": "huggingface_papers",
                },
            })
        return parsed

    def _parse_datasets(self, datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse HF datasets search results into paper-like entries."""
        parsed = []
        for ds in datasets:
            name = ds.get("id", "")
            description = ds.get("description", "")
            if not name:
                continue
            parsed.append({
                "title": f"Dataset: {name.split('/')[-1] if '/' in name else name}",
                "abstract": description[:1000] if description else f"A dataset on Hugging Face: {name}",
                "authors": [ds.get("author", "")] if ds.get("author") else [],
                "source": "huggingface",
                "source_id": name,
                "doi": None,
                "url": f"https://huggingface.co/datasets/{name}",
                "published_at": ds.get("createdAt", ""),
                "categories": ds.get("tags", []),
                "citations_count": ds.get("downloads", 0),
                "metadata": {"source": "huggingface_datasets", "likes": ds.get("likes", 0)},
            })
        return parsed


class CrossRefSource:
    """CrossRef API client. No API key required (public API)."""

    BASE_URL = "https://api.crossref.org/works"

    async def search(
        self, query: str, rows: int = 100, offset: int = 0,
    ) -> List[Dict[str, Any]]:
        params = {
            "query": query,
            "rows": rows,
            "offset": offset,
            "sort": "published",
            "order": "desc",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()

        data = resp.json()
        items = data.get("message", {}).get("items", [])
        return self._parse_items(items)

    def _parse_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        parsed = []
        for item in items:
            title = item.get("title") or [""]
            parsed.append({
                "title": title[0] if title else "",
                "abstract": item.get("abstract", "") or "",
                "authors": [
                    a.get("given", "") + " " + a.get("family", "")
                    for a in item.get("author", [])
                ],
                "source": "crossref",
                "source_id": item.get("DOI", ""),
                "doi": item.get("DOI"),
                "url": next(iter(item.get("resource", {}).values()), None),
                "published_at": (
                    item.get("published-print", {}).get("date-parts", [[None]])[0]
                    or item.get("published-online", {}).get("date-parts", [[None]])[0]
                    or [None]
                )[0],
                "citations_count": item.get("is-referenced-by-count", 0),
                "categories": item.get("subject", []),
                "metadata": {"publisher": item.get("publisher"), "type": item.get("type")},
            })
        return parsed
