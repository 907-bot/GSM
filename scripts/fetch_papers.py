"""Fetch real papers from CrossRef (no API key) and arXiv to seed the database.
Usage:  python -m scripts.fetch_papers [--query "machine learning"] [--count 20]
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.sources import CrossRefSource, ArxivSource, OpenAlexSource


async def fetch_and_save(query: str, count: int):
    print(f"\n{'='*60}")
    print(f"Fetching {count} papers for query: '{query}'")
    print(f"{'='*60}\n")

    total = 0

    # 1. CrossRef (no API key needed)
    print("📡 CrossRef  →  ", end="", flush=True)
    try:
        cr = CrossRefSource()
        papers = await cr.search(query, rows=min(count, 100))
        print(f"{len(papers)} papers")
        for p in papers:
            print(f"   [{p['source']}] {p['title'][:70]}")
            if p.get("doi"):
                print(f"           DOI: {p['doi']}")
        total += len(papers)
    except Exception as e:
        print(f"FAILED: {e}")

    # 2. arXiv (no API key needed)
    print("\n📡 arXiv     →  ", end="", flush=True)
    try:
        arxiv = ArxivSource()
        papers = await arxiv.search(query, max_results=min(count, 100))
        print(f"{len(papers)} papers")
        for p in papers[:5]:
            print(f"   [{p['source']}] {p['title'][:70]}")
        if len(papers) > 5:
            print(f"   ... and {len(papers) - 5} more")
        total += len(papers)
    except Exception as e:
        print(f"FAILED: {e}")

    # 3. OpenAlex (with API key if set)
    print("\n📡 OpenAlex  →  ", end="", flush=True)
    try:
        oa = OpenAlexSource(api_key="PDtKVhilySvi5NErCpiZbD")
        papers = await oa.search(query, per_page=min(count, 100))
        print(f"{len(papers)} papers")
        for p in papers[:5]:
            print(f"   [{p['source']}] {p['title'][:70]}")
        if len(papers) > 5:
            print(f"   ... and {len(papers) - 5} more")
        total += len(papers)
    except Exception as e:
        print(f"FAILED: {e}")

    print(f"\n{'='*60}")
    print(f"Total papers fetched: {total}")
    print(f"{'='*60}")

    return total


def main():
    parser = argparse.ArgumentParser(description="Fetch research papers from public APIs")
    parser.add_argument("--query", default="machine learning transformers", help="Search query")
    parser.add_argument("--count", type=int, default=10, help="Papers per source")
    args = parser.parse_args()

    total = asyncio.run(fetch_and_save(args.query, args.count))
    sys.exit(0 if total > 0 else 1)


if __name__ == "__main__":
    main()
