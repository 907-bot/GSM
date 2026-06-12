#!/usr/bin/env python3
"""
download_papers.py — Fetch real research papers from live APIs and ingest them into GSM-OS.

Sources used (all free / no strict key required):
  - ArXiv       (always free, no key)
  - OpenAlex    (uses OPENALEX_API_KEY from .env if set)
  - Semantic Scholar (uses SEMANTIC_SCHOLAR_API_KEY if set, otherwise free tier)

Usage:
  python scripts/download_papers.py
  python scripts/download_papers.py --topics "quantum computing,CRISPR" --limit 10
"""
import asyncio
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.sources import ArxivSource, OpenAlexSource, SemanticScholarSource
from src.agents.research_agent import BaseResearchAgent
from src.config import settings


DEFAULT_TOPICS = [
    "large language models",
    "CRISPR gene editing",
    "quantum computing",
    "drug discovery deep learning",
    "room temperature superconductor",
]


async def fetch_from_arxiv(topic: str, limit: int) -> list:
    """Fetch papers from ArXiv (always free, no key needed)."""
    source = ArxivSource()
    try:
        papers = await source.search(topic, max_results=limit)
        print(f"  [ArXiv]    '{topic}' → {len(papers)} papers")
        return papers
    except Exception as e:
        print(f"  [ArXiv]    '{topic}' → ERROR: {e}")
        return []


async def fetch_from_openalex(topic: str, limit: int) -> list:
    """Fetch papers from OpenAlex (uses API key from .env if available)."""
    source = OpenAlexSource(api_key=settings.OPENALEX_API_KEY)
    try:
        papers = await source.search(topic, per_page=min(limit, 50))
        print(f"  [OpenAlex] '{topic}' → {len(papers)} papers"
              + (" (authenticated)" if settings.OPENALEX_API_KEY else " (unauthenticated)"))
        return papers
    except Exception as e:
        print(f"  [OpenAlex] '{topic}' → ERROR: {e}")
        return []


async def fetch_from_semantic_scholar(topic: str, limit: int) -> list:
    """Fetch papers from Semantic Scholar (uses API key if available, else free tier)."""
    source = SemanticScholarSource(api_key=settings.SEMANTIC_SCHOLAR_API_KEY)
    try:
        papers = await source.search(topic, limit=min(limit, 100))
        print(f"  [S2]       '{topic}' → {len(papers)} papers"
              + (" (authenticated)" if settings.SEMANTIC_SCHOLAR_API_KEY else " (free tier)"))
        return papers
    except Exception as e:
        print(f"  [S2]       '{topic}' → ERROR: {e}")
        return []


async def ingest_papers(papers: list, domain: str = "general") -> dict:
    """Process and store papers into Qdrant + Neo4j via research agent."""
    agent = BaseResearchAgent(domain=domain, keywords=[])
    stored = 0
    failed = 0

    for paper_data in papers:
        if not paper_data.get("title"):
            continue
        try:
            paper = await agent.process_paper(paper_data)
            if paper:
                stored += 1
                print(f"    ✓ {paper.title[:70]}...")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"    ✗ {paper_data.get('title', 'unknown')[:60]}... → {e}")

    return {"stored": stored, "failed": failed}


async def main(topics: list, limit_per_source: int):
    print("\n══════════════════════════════════════════════════════════")
    print("  GSM-OS Live Data Downloader")
    print(f"  Topics: {topics}")
    print(f"  Limit per source per topic: {limit_per_source}")
    print(f"  OpenAlex key:          {'✓ set' if settings.OPENALEX_API_KEY else '✗ not set (using unauthenticated)'}")
    print(f"  Semantic Scholar key:  {'✓ set' if settings.SEMANTIC_SCHOLAR_API_KEY else '✗ not set (using free tier)'}")
    print("══════════════════════════════════════════════════════════\n")

    total_stored = 0
    total_failed = 0

    for topic in topics:
        print(f"\n▶  Topic: {topic}")

        # Fetch from all sources concurrently
        arxiv_papers, openalex_papers, s2_papers = await asyncio.gather(
            fetch_from_arxiv(topic, limit_per_source),
            fetch_from_openalex(topic, limit_per_source),
            fetch_from_semantic_scholar(topic, limit_per_source),
        )

        all_papers = arxiv_papers + openalex_papers + s2_papers

        # Deduplicate by title (case-insensitive)
        seen_titles = set()
        unique_papers = []
        for p in all_papers:
            title_key = p.get("title", "").lower().strip()
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_papers.append(p)

        print(f"  → {len(all_papers)} fetched, {len(unique_papers)} unique after dedup")
        print(f"  Ingesting into Qdrant + Neo4j...")

        stats = await ingest_papers(unique_papers, domain=topic.split()[0])
        total_stored += stats["stored"]
        total_failed += stats["failed"]

    print("\n══════════════════════════════════════════════════════════")
    print(f"  ✅ Done!  Stored: {total_stored}  |  Failed: {total_failed}")
    print("══════════════════════════════════════════════════════════\n")
    print("  Verify with:  curl http://localhost:8000/memory/statistics")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download live research papers into GSM-OS")
    parser.add_argument(
        "--topics",
        type=str,
        default=",".join(DEFAULT_TOPICS),
        help="Comma-separated list of topics to search",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max papers per source per topic (default: 5)",
    )
    args = parser.parse_args()

    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    asyncio.run(main(topics=topics, limit_per_source=args.limit))
