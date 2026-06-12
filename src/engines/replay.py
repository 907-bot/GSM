from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import structlog
from ..bus import event_bus
from ..events import Event, EventType
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory
from ..services.embeddings import embedding_service

logger = structlog.get_logger()


class ReplayEngine:
    """Scientific replay system for memory consolidation."""
    
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
    
    async def replay_memories(
        self,
        time_window_days: int = 7,
        sample_size: int = 100,
    ) -> Dict[str, Any]:
        """Replay recent memories to consolidate knowledge."""
        logger.info("Starting replay cycle", time_window=time_window_days)
        await event_bus.publish(Event(
            type=EventType.REPLAY_STARTED,
            data={"operation": "replay", "time_window_days": time_window_days},
            room="replay",
        ))
        
        # Get recent papers
        recent_papers = await self.episodic.get_recent_papers(limit=sample_size)
        
        if not recent_papers:
            return {"status": "no_memories", "consolidated": 0}
        
        # Extract embeddings for clustering
        embeddings = []
        paper_ids = []
        
        for paper in recent_papers:
            if paper["payload"].get("type") == "paper":
                # Generate embedding for clustering
                embedding = await embedding_service.embed_paper(
                    paper["payload"].get("title", ""),
                    paper["payload"].get("abstract", ""),
                )
                embeddings.append(embedding)
                paper_ids.append(paper["id"])
        
        if not embeddings:
            return {"status": "no_embeddings", "consolidated": 0}
        
        # Find shared concepts between papers
        shared_concepts = await self._find_shared_concepts(recent_papers)
        
        # Create new graph edges based on shared concepts
        new_edges = await self._create_graph_edges(shared_concepts)
        
        # Consolidate knowledge by strengthening relationships
        consolidated = await self._consolidate_relationships(shared_concepts)
        
        result = {
            "status": "completed",
            "papers_replayed": len(recent_papers),
            "shared_concepts_found": len(shared_concepts),
            "new_edges_created": new_edges,
            "relationships_consolidated": consolidated,
            "timestamp": datetime.now().isoformat(),
        }
        
        await event_bus.publish(Event(
            type=EventType.REPLAY_COMPLETED,
            data=result,
            room="replay",
        ))
        logger.info("Replay cycle completed", result=result)
        return result
    
    async def _find_shared_concepts(
        self, papers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find concepts that appear across multiple papers."""
        concept_counts: Dict[str, List[str]] = {}
        
        for paper in papers:
            paper_id = paper["id"]
            concepts = paper["payload"].get("categories", [])
            
            for concept in concepts:
                if concept not in concept_counts:
                    concept_counts[concept] = []
                concept_counts[concept].append(paper_id)
        
        # Find concepts appearing in multiple papers
        shared = []
        for concept, paper_ids in concept_counts.items():
            if len(paper_ids) > 1:
                shared.append({
                    "concept": concept,
                    "paper_ids": paper_ids,
                    "frequency": len(paper_ids),
                })
        
        return sorted(shared, key=lambda x: x["frequency"], reverse=True)
    
    async def _create_graph_edges(self, shared_concepts: List[Dict[str, Any]]) -> int:
        """Create new edges in the knowledge graph based on shared concepts."""
        edges_created = 0
        
        for concept_data in shared_concepts[:50]:  # Limit to top 50
            paper_ids = concept_data["paper_ids"]
            concept = concept_data["concept"]
            
            # Create edges between papers that share this concept
            for i in range(len(paper_ids)):
                for j in range(i + 1, min(i + 5, len(paper_ids))):  # Limit connections
                    await self.semantic.create_relationship(
                        paper_ids[i],
                        paper_ids[j],
                        "SHARES_CONCEPT",
                        {"concept": concept, "strength": concept_data["frequency"]},
                    )
                    edges_created += 1
        
        return edges_created
    
    async def _consolidate_relationships(self, shared_concepts: List[Dict[str, Any]]) -> int:
        """Strengthen relationships based on repeated co-occurrence."""
        consolidated = 0
        
        for concept_data in shared_concepts:
            concept = concept_data["concept"]
            frequency = concept_data["frequency"]
            
            # Strengthen the concept node
            await self.semantic.create_concept(
                concept,
                "shared_concept",
                {"frequency": frequency, "last_reinforced": datetime.now().isoformat()},
            )
            consolidated += 1
        
        return consolidated
    
    async def dream(self, duration_minutes: int = 30) -> Dict[str, Any]:
        """Digital dreaming - explore random paths in the knowledge graph."""
        logger.info("Starting dream cycle", duration=duration_minutes)
        await event_bus.publish(Event(
            type=EventType.REPLAY_STARTED,
            data={"operation": "dream", "duration_minutes": duration_minutes},
            room="replay",
        ))
        
        dream_results = {
            "paths_explored": 0,
            "connections_discovered": 0,
            "hypotheses_generated": 0,
        }
        
        # Get random concepts to explore
        stats = await self.semantic.get_statistics()
        
        if stats["concepts"] == 0:
            return dream_results
        
        # Explore random paths
        for _ in range(10):
            try:
                # Get a random starting concept
                start_concept = await self._get_random_concept()
                if not start_concept:
                    continue
                
                # Find paths from this concept
                paths = await self.semantic.find_path(
                    start_concept,
                    start_concept,  # Find loops
                    max_depth=4,
                )
                
                dream_results["paths_explored"] += len(paths)
                
                # Discover new connections
                hidden = await self.semantic.find_hidden_relationships()
                dream_results["connections_discovered"] += len(hidden)
                
            except Exception as e:
                logger.error("Dream exploration failed", error=str(e))
        
        await event_bus.publish(Event(
            type=EventType.REPLAY_COMPLETED,
            data=dream_results,
            room="replay",
        ))
        logger.info("Dream cycle completed", results=dream_results)
        return dream_results
    
    async def _get_random_concept(self) -> Optional[str]:
        """Get a random concept from the graph."""
        try:
            with self.semantic.driver.session(database="scientific_graph") as session:
                result = session.run(
                    "MATCH (c:Concept) RETURN c.name AS name ORDER BY rand() LIMIT 1"
                )
                record = result.single()
                return record["name"] if record else None
        except Exception as e:
            logger.error("Failed to get random concept", error=str(e))
            return None
