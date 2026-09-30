from neo4j import GraphDatabase
from typing import List, Optional, Dict, Any
from ..config import settings
from ..bus import event_bus
from ..events import Event, EventType
import structlog

logger = structlog.get_logger()


class SemanticMemory:
    """Neo4j-based semantic memory for scientific concepts and relationships."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        self._ensure_constraints()
    
    def _ensure_constraints(self):
        """Create constraints and indexes if they don't exist."""
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE
                """)
                session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.doi)
                """)
                session.run("""
                    CREATE INDEX IF NOT EXISTS FOR (a:Author) ON (a.name)
                """)
                logger.info("Neo4j constraints and indexes ensured")
        except Exception as e:
            logger.warning("Neo4j unavailable; semantic graph will use empty fallbacks", error=str(e))
    
    def close(self):
        """Close the driver connection."""
        self.driver.close()
    
    async def create_concept(self, name: str, concept_type: str, properties: Dict[str, Any] = None) -> str:
        """Create a concept node."""
        props = properties or {}
        props["name"] = name
        props["type"] = concept_type
        
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    SET c += $props
                    RETURN c.name AS name
                    """,
                    name=name,
                    props=props,
                )
                record = result.single()
                logger.info("Created concept", name=name, type=concept_type)
                await event_bus.publish(Event(
                    type=EventType.GRAPH_CONCEPT_CREATED,
                    data={"concept": name, "type": concept_type, "properties": props},
                    room="graph",
                ))
                return record["name"]
        except Exception as e:
            logger.warning("Neo4j create_concept unavailable", name=name, error=str(e))
            return name
    
    async def create_relationship(
        self,
        source_name: str,
        target_name: str,
        relationship_type: str,
        properties: Dict[str, Any] = None
    ) -> bool:
        """Create a relationship between two concepts."""
        props = properties or {}
        
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                session.run(
                    f"""
                    MATCH (a:Concept {{name: $source_name}})
                    MATCH (b:Concept {{name: $target_name}})
                    MERGE (a)-[r:{relationship_type}]->(b)
                    SET r += $props
                    """,
                    source_name=source_name,
                    target_name=target_name,
                    props=props,
                )
                logger.info(
                    "Created relationship",
                    source=source_name,
                    target=target_name,
                    type=relationship_type,
                )
                await event_bus.graph_relationship(source=source_name, target=target_name, rel_type=relationship_type)
                return True
        except Exception as e:
            logger.warning(
                "Neo4j create_relationship unavailable",
                source=source_name,
                target=target_name,
                error=str(e),
            )
            return False
    
    async def link_paper_to_concepts(self, paper_id: str, concepts: List[str]) -> bool:
        """Link a paper to its concepts."""
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                for concept_name in concepts:
                    session.run(
                        """
                        MERGE (p:Paper {id: $paper_id})
                        MERGE (c:Concept {name: $concept_name})
                        MERGE (p)-[:MENTIONS]->(c)
                        """,
                        paper_id=paper_id,
                        concept_name=concept_name,
                    )
                    await event_bus.graph_relationship(source=str(paper_id), target=concept_name, rel_type="related_to")
                logger.info("Linked paper to concepts", paper_id=paper_id, concept_count=len(concepts))
                return True
        except Exception as e:
            logger.warning("Neo4j link_paper_to_concepts unavailable", paper_id=paper_id, error=str(e))
            return False
    
    async def find_path(self, source: str, target: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Find paths between two concepts.
        
        Note: max_depth is validated as integer to prevent Cypher injection
        (Neo4j 5.x does not support parameterized path lengths in MATCH patterns).
        """
        max_depth = max(1, min(20, int(max_depth)))
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run(
                f"""
                MATCH path = shortestPath(
                    (a:Concept {{name: $source}})-[*1..{max_depth}]-(b:Concept {{name: $target}})
                )
                RETURN path, length(path) AS length
                """,
                source=source,
                target=target,
            )
            
                paths = []
                for record in result:
                    path = record["path"]
                    paths.append({
                        "nodes": [node["name"] for node in path.nodes],
                        "relationships": [
                            {
                                "type": rel.type,
                                "start": rel.start_node["name"],
                                "end": rel.end_node["name"],
                            }
                            for rel in path.relationships
                        ],
                        "length": record["length"],
                    })
                
                return paths
        except Exception as e:
            logger.warning("Neo4j find_path unavailable", source=source, target=target, error=str(e))
            return []
    
    async def find_hidden_relationships(self, min_path_length: int = 2, max_path_length: int = 4) -> List[Dict[str, Any]]:
        """Find potential hidden relationships between concepts."""
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run(
                """
                MATCH (a:Concept)-[r1]-(b:Concept)-[r2]-(c:Concept)
                WHERE a <> c
                AND NOT (a)-[:DIRECTLY_CONNECTED]-(c)
                AND length(shortestPath((a)-[*]-(c))) >= $min_len
                AND length(shortestPath((a)-[*]-(c))) <= $max_len
                RETURN a.name AS source, c.name AS target, 
                       collect(distinct type(r1)) AS intermediate_types,
                       count(*) AS strength
                ORDER BY strength DESC
                LIMIT 50
                """,
                min_len=min_path_length,
                max_len=max_path_length,
            )
            
                return [
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "intermediate_types": record["intermediate_types"],
                        "strength": record["strength"],
                    }
                    for record in result
                ]
        except Exception as e:
            logger.warning("Neo4j hidden relationship search unavailable", error=str(e))
            return []
    
    async def get_concept_neighbors(self, concept_name: str, depth: int = 1) -> Dict[str, Any]:
        """Get neighboring concepts.
        
        Note: depth is validated as integer to prevent Cypher injection
        (Neo4j 5.x does not support parameterized path lengths in MATCH patterns).
        """
        depth = max(1, min(10, int(depth)))
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run(
                f"""
                MATCH path = (c:Concept {{name: $name}})-[*1..{depth}]-(neighbor:Concept)
                RETURN DISTINCT neighbor.name AS name, neighbor.type AS type,
                       length(path) AS distance
                ORDER BY distance
                """,
                name=concept_name,
            )
            
                return {
                    "concept": concept_name,
                    "neighbors": [
                        {
                            "name": record["name"],
                            "type": record["type"],
                            "distance": record["distance"],
                        }
                        for record in result
                    ],
                }
        except Exception as e:
            logger.warning("Neo4j neighbor lookup unavailable", concept=concept_name, error=str(e))
            return {"concept": concept_name, "neighbors": []}
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                concept_count = session.run("MATCH (c:Concept) RETURN count(c) AS count").single()["count"]
                paper_count = session.run("MATCH (p:Paper) RETURN count(p) AS count").single()["count"]
                relationship_count = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
                
                return {
                    "concepts": concept_count,
                    "papers": paper_count,
                    "relationships": relationship_count,
                }
        except Exception as e:
            logger.warning("Neo4j statistics unavailable", error=str(e))
            return {"concepts": 0, "papers": 0, "relationships": 0}
