from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from ..bus import event_bus
from ..events import Event, EventType
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..services.embeddings import embedding_service

logger = structlog.get_logger()


class GraphDiscoveryEngine:
    """Engine for discovering hidden patterns in the scientific graph."""
    
    def __init__(self):
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()
    
    async def discover_hidden_paths(
        self,
        source_concept: str,
        target_concept: str,
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """Discover hidden paths between concepts."""
        paths = await self.semantic.find_path(
            source_concept,
            target_concept,
            max_depth=max_depth,
        )
        
        # Enrich paths with additional context
        enriched_paths = []
        for path in paths:
            enriched_path = await self._enrich_path(path)
            enriched_paths.append(enriched_path)
            nodes = path.get("nodes", [])
            for i in range(len(nodes) - 1):
                await event_bus.graph_relationship(nodes[i], nodes[i + 1], "HIDDEN_PATH")
        
        logger.info(
            "Hidden path discovery completed",
            source=source_concept,
            target=target_concept,
            paths_found=len(enriched_paths),
        )
        
        return enriched_paths
    
    async def _enrich_path(self, path: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a path with additional context."""
        enriched = path.copy()
        
        # Add concept types
        for node_name in path.get("nodes", []):
            # Would query Neo4j for node details
            enriched.setdefault("node_details", {})[node_name] = {
                "type": "concept",
                "importance": 0.5,
            }
        
        return enriched
    
    async def detect_emerging_clusters(
        self,
        time_window_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Detect emerging concept clusters."""
        # Get recent papers
        recent_papers = await self.episodic.get_recent_papers(limit=200)
        
        # Extract concepts
        concept_counts: Dict[str, int] = {}
        concept_temporal: Dict[str, List[datetime]] = {}
        
        for paper in recent_papers:
            concepts = paper.get("payload", {}).get("categories", [])
            for concept in concepts:
                concept_counts[concept] = concept_counts.get(concept, 0) + 1
                
                # Track temporal distribution
                published = paper.get("payload", {}).get("published_at")
                if published:
                    if concept not in concept_temporal:
                        concept_temporal[concept] = []
                    concept_temporal[concept].append(datetime.fromisoformat(published))
        
        # Identify emerging clusters (concepts with increasing frequency)
        emerging = []
        for concept, count in concept_counts.items():
            if count >= 5:  # Minimum threshold
                temporal_data = concept_temporal.get(concept, [])
                
                # Calculate recency score
                if temporal_data:
                    recent_count = sum(
                        1 for t in temporal_data
                        if (datetime.now() - t).days <= 7
                    )
                    recency_score = recent_count / len(temporal_data)
                else:
                    recency_score = 0
                
                emerging.append({
                    "concept": concept,
                    "paper_count": count,
                    "recency_score": recency_score,
                    "emergence_score": count * recency_score,
                })
        
        # Sort by emergence score
        emerging.sort(key=lambda x: x["emergence_score"], reverse=True)
        
        logger.info(
            "Emerging cluster detection completed",
            clusters_found=len(emerging),
        )

        for cluster in emerging[:20]:
            await event_bus.publish(Event(
                type=EventType.GRAPH_CLUSTER_DETECTED,
                data=cluster,
                room="graph",
            ))

        return emerging[:20]  # Return top 20
    
    async def find_missing_links(self) -> List[Dict[str, Any]]:
        """Find potential missing links in the knowledge graph."""
        hidden = await self.semantic.find_hidden_relationships(
            min_path_length=2,
            max_path_length=3,
        )
        
        # Enrich with confidence scores
        missing_links = []
        for link in hidden:
            missing_links.append({
                "source": link["source"],
                "target": link["target"],
                "confidence": min(0.9, link["strength"] / 10),
                "evidence_types": link.get("intermediate_types", []),
                "recommendation": f"Investigate potential link between {link['source']} and {link['target']}",
            })
        
        return missing_links
    
    async def analyze_graph_health(self) -> Dict[str, Any]:
        """Analyze the health and quality of the knowledge graph."""
        stats = await self.semantic.get_statistics()
        
        # Calculate metrics
        density = self._calculate_density(stats)
        connectivity = await self._calculate_connectivity()
        
        return {
            "statistics": stats,
            "density": density,
            "connectivity": connectivity,
            "health_score": (density + connectivity) / 2,
            "recommendations": self._generate_recommendations(stats, density),
        }
    
    def _calculate_density(self, stats: Dict[str, int]) -> float:
        """Calculate graph density."""
        nodes = stats.get("concepts", 0) + stats.get("papers", 0)
        edges = stats.get("relationships", 0)
        
        if nodes < 2:
            return 0.0
        
        max_edges = nodes * (nodes - 1) / 2
        return edges / max_edges if max_edges > 0 else 0.0
    
    async def _calculate_connectivity(self) -> float:
        """Calculate graph connectivity."""
        # Placeholder - would perform actual connectivity analysis
        return 0.5
    
    def _generate_recommendations(
        self, stats: Dict[str, int], density: float
    ) -> List[str]:
        """Generate recommendations for improving the graph."""
        recommendations = []
        
        if stats.get("concepts", 0) < 100:
            recommendations.append("Add more concept nodes from recent literature")
        
        if stats.get("relationships", 0) < 500:
            recommendations.append("Discover and create more relationships")
        
        if density < 0.01:
            recommendations.append("Graph is sparse - consider adding more connections")
        
        return recommendations
    
    async def visualize_subgraph(
        self,
        center_concept: str,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """Generate data for visualizing a subgraph."""
        neighbors = await self.semantic.get_concept_neighbors(
            center_concept,
            depth=depth,
        )
        
        nodes = []
        edges = []
        
        # Add center node
        nodes.append({
            "id": center_concept,
            "label": center_concept,
            "type": "center",
        })
        
        # Add neighbors
        for neighbor in neighbors.get("neighbors", []):
            nodes.append({
                "id": neighbor["name"],
                "label": neighbor["name"],
                "type": neighbor.get("type", "concept"),
                "distance": neighbor.get("distance", 1),
            })
            
            # Add edge
            edges.append({
                "source": center_concept,
                "target": neighbor["name"],
                "distance": neighbor.get("distance", 1),
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "center": center_concept,
        }
