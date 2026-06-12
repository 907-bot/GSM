"""Standalone test: fetch papers from CrossRef (no API key), arXiv, OpenAlex.
Usage:  python3 scripts/test_sources.py
"""
import asyncio
import httpx


class CrossRefSource:
    BASE_URL = "https://api.crossref.org/works"

    async def search(self, query: str, rows: int = 5) -> list:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(self.BASE_URL, params={"query": query, "rows": rows})
            r.raise_for_status()
        items = r.json().get("message", {}).get("items", [])
        result = []
        for item in items:
            title = (item.get("title") or [""])[0]
            doi = item.get("DOI", "")
            print(f"  ✅ CrossRef | {title[:75]}")
            if doi:
                print(f"              DOI: {doi}")
            result.append(item)
        return result


class ArxivSource:
    BASE_URL = "https://export.arxiv.org/api/query"

    async def search(self, query: str, max_results: int = 5) -> list:
        import xml.etree.ElementTree as ET
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(self.BASE_URL, params={
                "search_query": f"all:{query}", "max_results": max_results,
                "sortBy": "submittedDate", "sortOrder": "descending",
            })
            r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip()
            print(f"  ✅ arXiv    | {title[:75]}")
            papers.append(entry)
        return papers


class OpenAlexSource:
    BASE_URL = "https://api.openalex.org/works"

    async def search(self, query: str, api_key: str = "", per_page: int = 5) -> list:
        params = {"search": query, "per_page": per_page}
        if api_key:
            params["mailto"] = api_key
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(self.BASE_URL, params=params)
            r.raise_for_status()
        works = r.json().get("results", [])
        for w in works:
            print(f"  ✅ OpenAlex | {w.get('title', '')[:75]}")
        return works


async def main():
    query = "machine learning transformers"

    print(f"\n{'='*60}")
    print(f"  Testing all sources with query: '{query}'")
    print(f"{'='*60}\n")

    # 1. CrossRef (no API key)
    print("📡 CrossRef (no API key needed):")
    try:
        await CrossRefSource().search(query)
    except Exception as e:
        print(f"  ❌ FAILED: {e}")

    print("\n📡 arXiv (no API key needed):")
    try:
        await ArxivSource().search(query)
    except Exception as e:
        print(f"  ❌ FAILED: {e}")

    print("\n📡 OpenAlex (with mailto for rate limit):")
    try:
        await OpenAlexSource().search(query, api_key="PDtKVhilySvi5NErCpiZbD")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")

    print(f"\n{'='*60}")
    print("  Done!")
    print(f"{'='*60}")


asyncio.run(main())
