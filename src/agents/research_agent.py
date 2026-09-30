from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from ..config import settings
from ..models import Paper, PaperSource, PaperStatus
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory
from ..services.embeddings import embedding_service
from ..bus import event_bus
from ..events import EventType, Event
from ..engines.quality import QualityPipeline
from ..engines.extraction import scientific_extractor
from ..memory.graph_schema import graph_schema
from .sources import ArxivSource, SemanticScholarSource, OpenAlexSource, PubMedSource, CrossRefSource
from .sources_extended import BioRxivSource, MedRxivSource, CORESource

logger = structlog.get_logger()


class BaseResearchAgent:
    """Base class for domain-specific research agents."""
    
    def __init__(self, domain: str, keywords: List[str]):
        self.domain = domain
        self.keywords = keywords
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.quality = QualityPipeline()
        self.sources = {
            "arxiv": ArxivSource(),
            "semantic_scholar": SemanticScholarSource(
                api_key=settings.SEMANTIC_SCHOLAR_API_KEY
            ),
            "openalex": OpenAlexSource(
                api_key=settings.OPENALEX_API_KEY
            ),
            "pubmed": PubMedSource(api_key=settings.NCBI_API_KEY),
            "crossref": CrossRefSource(),
            "biorxiv": BioRxivSource(),
            "medrxiv": MedRxivSource(),
            "core": CORESource(api_key=settings.CORE_API_KEY),
        }
    
    async def search_papers(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Paper]:
        """Search for papers across configured sources."""
        if sources is None:
            sources = ["arxiv", "semantic_scholar", "openalex"]

        total_sources = len(sources)
        await event_bus.agent_event(self.domain, EventType.AGENT_SEARCH_STARTED,
            query=query, sources=sources, total_sources=total_sources)
        all_papers = []

        for idx, source_name in enumerate(sources):
            await event_bus.publish(Event(
                type=EventType.AGENT_SOURCE_PROGRESS,
                data={
                    "domain": self.domain,
                    "query": query,
                    "source": source_name,
                    "current": idx + 1,
                    "total": total_sources,
                    "status": "querying",
                },
                room="discovery",
                source=f"agent.{self.domain}",
            ))
            try:
                source = self.sources.get(source_name)
                if source:
                    papers = await source.search(query, max_results=limit)
                    all_papers.extend(papers)
                    await event_bus.publish(Event(
                        type=EventType.AGENT_SOURCE_PROGRESS,
                        data={
                            "domain": self.domain,
                            "query": query,
                            "source": source_name,
                            "current": idx + 1,
                            "total": total_sources,
                            "status": "done",
                            "count": len(papers),
                        },
                        room="discovery",
                        source=f"agent.{self.domain}",
                    ))
                    await event_bus.agent_event(self.domain, EventType.AGENT_PAPER_FOUND,
                        source=source_name, count=len(papers), query=query)
                    logger.info(
                        "Fetched papers from source",
                        source=source_name,
                        count=len(papers),
                    )
            except Exception as e:
                await event_bus.publish(Event(
                    type=EventType.AGENT_SOURCE_PROGRESS,
                    data={
                        "domain": self.domain,
                        "query": query,
                        "source": source_name,
                        "current": idx + 1,
                        "total": total_sources,
                        "status": "failed",
                        "error": str(e),
                    },
                    room="discovery",
                    source=f"agent.{self.domain}",
                ))
                logger.error(
                    "Failed to fetch from source",
                    source=source_name,
                    error=str(e),
                )

        return all_papers
    
    async def process_paper(self, paper_data: Dict[str, Any]) -> Optional[Paper]:
        """Process and store a paper through the quality pipeline."""
        try:
            await event_bus.agent_event(self.domain, EventType.PAPER_FETCHED,
                title=paper_data.get("title", "")[:80])
            
            # Create paper model (generates UUID)
            paper = Paper(
                title=paper_data.get("title", ""),
                abstract=paper_data.get("abstract"),
                authors=paper_data.get("authors", []),
                source=PaperSource(paper_data.get("source", "arxiv")),
                source_id=paper_data.get("source_id", ""),
                url=paper_data.get("url"),
                doi=paper_data.get("doi"),
                categories=paper_data.get("categories", []),
                citations_count=paper_data.get("citations_count", 0),
                metadata=paper_data.get("metadata", {}),
            )
            
            paper_dict = paper.model_dump()
            
            # Generate embedding
            embedding = await embedding_service.embed_paper(
                paper.title,
                paper.abstract,
            )
            await event_bus.agent_event(self.domain, EventType.PAPER_EMBEDDED,
                paper_id=str(paper.id), title=paper.title[:50])
            
            # Run quality pipeline (validates, deduplicates, stores)
            accepted, result, message = await self.quality.process_paper(
                paper_dict,
                embedding=embedding,
                source=paper_data.get("source", "arxiv"),
                source_id=paper_data.get("source_id", ""),
            )
            
            if not accepted:
                if message.startswith("Merged duplicate") and result:
                    paper.embedding_id = str(result.get("id", "")) if result else str(paper.id)
                    paper.status = PaperStatus.INDEXED
                    await event_bus.agent_event(self.domain, EventType.PAPER_INDEXED,
                        paper_id=str(paper.id), title=paper.title[:50], concepts=paper.categories)
                    logger.info("Paper merged with existing record", reason=message)
                    return paper
                await event_bus.agent_event(self.domain, EventType.PAPER_FAILED,
                    title=paper.title[:80], error=message)
                logger.info("Paper rejected by quality pipeline", reason=message)
                return None
            
            paper.embedding_id = str(result.get("id", "")) if result else str(paper.id)
            paper.status = PaperStatus.INDEXED

            # Store full paper in Neo4j graph with authors + categories
            await graph_schema.upsert_paper_full(
                paper_id=str(paper.id),
                title=paper.title,
                doi=paper.doi,
                authors=paper.authors,
                published_at=str(paper.published_at) if paper.published_at else None,
                source=paper.source.value,
                categories=paper.categories,
                citations_count=paper.citations_count,
            )

            # Extract and store concepts in semantic memory
            concepts = await self._extract_concepts(paper)
            if concepts:
                await self.semantic.link_paper_to_concepts(
                    str(paper.id),
                    concepts,
                )

            # Run scientific entity extraction (async, non-blocking)
            if paper.abstract:
                try:
                    await scientific_extractor.extract_from_paper(
                        paper_id=str(paper.id),
                        title=paper.title,
                        abstract=paper.abstract or "",
                        store_in_graph=True,
                    )
                except Exception as ext_err:
                    logger.warning(
                        "Entity extraction failed (non-fatal)",
                        paper_id=str(paper.id),
                        error=str(ext_err),
                    )
            
            await event_bus.agent_event(self.domain, EventType.PAPER_INDEXED,
                paper_id=str(paper.id), title=paper.title[:50], concepts=concepts)
            
            logger.info(
                "Processed paper through quality pipeline",
                paper_id=str(paper.id),
                title=paper.title[:50],
            )
            
            return paper
            
        except Exception as e:
            await event_bus.agent_event(self.domain, EventType.PAPER_FAILED,
                title=paper_data.get("title", "")[:80], error=str(e))
            logger.error(
                "Failed to process paper",
                title=paper_data.get("title", ""),
                error=str(e),
            )
            return None
    
    async def _extract_concepts(self, paper: Paper) -> List[str]:
        """Extract key concepts from a paper."""
        # This would use NLP to extract entities and concepts
        # For now, return categories as concepts
        concepts = list(paper.categories)
        
        # Add domain-specific concepts
        concepts.extend(self.keywords[:5])
        
        return list(set(concepts))
    
    async def run_search_cycle(self) -> Dict[str, Any]:
        """Run a complete search cycle for this agent's domain."""
        results = {
            "domain": self.domain,
            "papers_found": 0,
            "papers_processed": 0,
            "errors": 0,
        }

        total_keywords = len(self.keywords)
        for kidx, keyword in enumerate(self.keywords):
            await event_bus.publish(Event(
                type=EventType.AGENT_SEARCH_PROGRESS,
                data={
                    "domain": self.domain,
                    "keyword": keyword,
                    "current_keyword": kidx + 1,
                    "total_keywords": total_keywords,
                    "status": "searching",
                },
                room="discovery",
                source=f"agent.{self.domain}",
            ))
            papers = await self.search_papers(keyword)
            results["papers_found"] += len(papers)

            total_papers = len(papers)
            await event_bus.publish(Event(
                type=EventType.AGENT_SEARCH_PROGRESS,
                data={
                    "domain": self.domain,
                    "keyword": keyword,
                    "current_keyword": kidx + 1,
                    "total_keywords": total_keywords,
                    "status": "processing",
                    "total_papers": total_papers,
                },
                room="discovery",
                source=f"agent.{self.domain}",
            ))

            for pidx, paper_data in enumerate(papers):
                try:
                    paper_dict = paper_data.to_dict() if hasattr(paper_data, 'to_dict') else paper_data.model_dump()
                    await event_bus.publish(Event(
                        type=EventType.AGENT_SEARCH_PROGRESS,
                        data={
                            "domain": self.domain,
                            "keyword": keyword,
                            "current_keyword": kidx + 1,
                            "total_keywords": total_keywords,
                            "status": "processing_paper",
                            "current_paper": pidx + 1,
                            "total_papers": total_papers,
                            "paper_title": paper_dict.get("title", "")[:60],
                        },
                        room="discovery",
                        source=f"agent.{self.domain}",
                    ))
                    paper = await self.process_paper(paper_dict)
                    if paper:
                        results["papers_processed"] += 1
                except Exception as e:
                    results["errors"] += 1
                    await event_bus.agent_event(self.domain, EventType.AGENT_SEARCH_FAILED,
                        keyword=keyword, error=str(e))
                    logger.error("Failed to process paper", domain=self.domain, keyword=keyword, error=str(e))

        await event_bus.agent_event(self.domain, EventType.AGENT_SEARCH_COMPLETED, **results)
        return results


class BiologyAgent(BaseResearchAgent):
    """Agent for monitoring biology research."""
    
    def __init__(self):
        super().__init__(
            domain="biology",
            keywords=[
                "genetics",
                "molecular biology",
                "synthetic biology",
                "CRISPR",
                "gene therapy",
                "proteomics",
                "genomics",
                "cell biology",
            ],
        )


class AIAgent(BaseResearchAgent):
    """Agent for monitoring AI/ML research."""
    
    def __init__(self):
        super().__init__(
            domain="ai",
            keywords=[
                "large language models",
                "graph neural networks",
                "spiking neural networks",
                "reinforcement learning",
                "transformers",
                "deep learning",
                "machine learning",
            ],
        )


class MaterialsAgent(BaseResearchAgent):
    """Agent for monitoring materials science research."""
    
    def __init__(self):
        super().__init__(
            domain="materials",
            keywords=[
                "superconductors",
                "nanotechnology",
                "materials science",
                "metamaterials",
                "quantum materials",
                "2D materials",
                "polymers",
            ],
        )


class MedicineAgent(BaseResearchAgent):
    """Agent for monitoring medical research."""
    
    def __init__(self):
        super().__init__(
            domain="medicine",
            keywords=[
                "clinical studies",
                "drug discovery",
                "oncology",
                "immunotherapy",
                "precision medicine",
                "biomarkers",
                "therapeutics",
            ],
        )


class ChemistryAgent(BaseResearchAgent):
    """Agent for monitoring chemistry research."""
    
    def __init__(self):
        super().__init__(
            domain="chemistry",
            keywords=[
                "organic chemistry",
                "catalysis",
                "drug design",
                "chemical synthesis",
                "computational chemistry",
                "biochemistry",
            ],
        )


class PhysicsAgent(BaseResearchAgent):
    """Agent for monitoring physics research."""
    
    def __init__(self):
        super().__init__(
            domain="physics",
            keywords=[
                "quantum computing",
                "condensed matter",
                "particle physics",
                "astrophysics",
                "plasma physics",
                "optics",
            ],
        )


def get_all_agents() -> List[BaseResearchAgent]:
    """Get all available research agents."""
    return [
        BiologyAgent(),
        AIAgent(),
        MaterialsAgent(),
        MedicineAgent(),
        ChemistryAgent(),
        PhysicsAgent(),
    ]
