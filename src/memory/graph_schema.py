"""
Rich Neo4j graph schema for the Autonomous Scientific Discovery Platform.

Adds all node types and relation types from the vision document.
Run `await graph_schema.initialize()` on startup after SemanticMemory is connected.
"""

from neo4j import GraphDatabase
from typing import Dict, Any, List, Optional
from ..config import settings
import structlog

logger = structlog.get_logger()

# ──────────────────────────────────────────────────────────────────────────────
# Relation types supported in the graph
# ──────────────────────────────────────────────────────────────────────────────
RELATION_TYPES = [
    "USES",           # Paper/Method uses Dataset/Algorithm
    "PROPOSES",       # Paper proposes Method/Algorithm
    "CONTRADICTS",    # Finding contradicts another Finding
    "VALIDATES",      # Paper validates another Finding
    "COMPARES",       # Paper compares two Methods
    "EXTENDS",        # Paper extends another Paper/Method
    "CITES",          # Paper cites another Paper
    "OUTPERFORMS",    # Method outperforms another Method on Dataset
    "FAILS_ON",       # Method fails on Dataset
    "SUGGESTS",       # Finding suggests Hypothesis
    "MENTIONS",       # Paper mentions Concept (generic)
    "AUTHORED_BY",    # Paper authored by Author
    "AFFILIATED_WITH", # Author affiliated with Institution
    "STUDIES",        # Paper studies Disease/Drug
    "TREATS",         # Drug treats Disease
    "TARGETS",        # Drug targets Protein
    "ASSOCIATED_WITH", # Protein associated with Disease
    "EVALUATED_ON",   # Method evaluated on Dataset
    "MEASURED_BY",    # Result measured by Metric
    "PUBLISHED_IN",   # Paper published in Journal/Venue
]

# Node types in the graph
NODE_TYPES = [
    "Paper",
    "Author",
    "Institution",
    "Concept",
    "Disease",
    "Drug",
    "Protein",
    "Dataset",
    "Method",
    "Algorithm",
    "Finding",
    "Hypothesis",
    "Equation",
    "Metric",
    "Experiment",
    "Result",
    "Journal",
    "Venue",
]

# ──────────────────────────────────────────────────────────────────────────────
# Schema setup Cypher statements
# ──────────────────────────────────────────────────────────────────────────────
SCHEMA_STATEMENTS = [
    # Core paper nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.doi IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.title)",
    "CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.published_at)",
    "CREATE INDEX IF NOT EXISTS FOR (p:Paper) ON (p.source)",

    # Author nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (a:Author) ON (a.orcid)",

    # Institution nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Institution) REQUIRE i.name IS UNIQUE",

    # Concept nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (c:Concept) ON (c.type)",

    # Disease nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (d:Disease) ON (d.mesh_id)",

    # Drug nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (dr:Drug) REQUIRE dr.name IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (dr:Drug) ON (dr.drugbank_id)",

    # Protein nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Protein) REQUIRE pr.name IS UNIQUE",
    "CREATE INDEX IF NOT EXISTS FOR (pr:Protein) ON (pr.uniprot_id)",

    # Dataset nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (ds:Dataset) REQUIRE ds.name IS UNIQUE",

    # Method nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Method) REQUIRE m.name IS UNIQUE",

    # Algorithm nodes
    "CREATE INDEX IF NOT EXISTS FOR (al:Algorithm) ON (al.name)",

    # Metric nodes
    "CREATE INDEX IF NOT EXISTS FOR (mt:Metric) ON (mt.name)",

    # Finding nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Finding) REQUIRE f.id IS UNIQUE",

    # Hypothesis nodes
    "CREATE CONSTRAINT IF NOT EXISTS FOR (h:Hypothesis) REQUIRE h.id IS UNIQUE",

    # Experiment nodes
    "CREATE INDEX IF NOT EXISTS FOR (e:Experiment) ON (e.name)",

    # Journal / Venue nodes
    "CREATE INDEX IF NOT EXISTS FOR (j:Journal) ON (j.name)",
]


class GraphSchema:
    """Manages the Neo4j graph schema for the scientific knowledge graph."""

    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    async def initialize(self) -> Dict[str, Any]:
        """Create all constraints and indexes. Idempotent — safe to call multiple times."""
        results = {"created": [], "skipped": [], "failed": []}
        driver = self._get_driver()

        with driver.session(database=settings.NEO4J_DATABASE) as session:
            for stmt in SCHEMA_STATEMENTS:
                try:
                    session.run(stmt)
                    results["created"].append(stmt[:60])
                except Exception as e:
                    err = str(e)
                    if "already exists" in err.lower() or "equivalent" in err.lower():
                        results["skipped"].append(stmt[:60])
                    else:
                        results["failed"].append({"stmt": stmt[:60], "error": err})
                        logger.warning("Schema statement failed", stmt=stmt[:60], error=err)

        logger.info(
            "Graph schema initialized",
            created=len(results["created"]),
            skipped=len(results["skipped"]),
            failed=len(results["failed"]),
        )
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Rich node creation helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def upsert_author(self, name: str, orcid: Optional[str] = None,
                             affiliations: Optional[List[str]] = None) -> str:
        driver = self._get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (a:Author {name: $name})
                SET a.orcid = COALESCE($orcid, a.orcid)
                """,
                name=name, orcid=orcid,
            )
            # Link to institutions
            for inst in (affiliations or []):
                session.run(
                    """
                    MERGE (i:Institution {name: $inst})
                    MERGE (a:Author {name: $name})
                    MERGE (a)-[:AFFILIATED_WITH]->(i)
                    """,
                    name=name, inst=inst,
                )
        return name

    async def upsert_paper_full(
        self,
        paper_id: str,
        title: str,
        doi: Optional[str] = None,
        authors: Optional[List[str]] = None,
        published_at: Optional[str] = None,
        source: Optional[str] = None,
        categories: Optional[List[str]] = None,
        citations_count: int = 0,
    ) -> bool:
        """Create/update a Paper node and link its authors and concepts."""
        driver = self._get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            try:
                # Upsert paper node
                session.run(
                    """
                    MERGE (p:Paper {id: $id})
                    SET p.title = $title,
                        p.doi = COALESCE($doi, p.doi),
                        p.published_at = COALESCE($published_at, p.published_at),
                        p.source = COALESCE($source, p.source),
                        p.citations_count = $citations_count
                    """,
                    id=paper_id, title=title, doi=doi,
                    published_at=published_at, source=source,
                    citations_count=citations_count,
                )
                # Link authors
                for author_name in (authors or []):
                    if author_name.strip():
                        session.run(
                            """
                            MERGE (a:Author {name: $author})
                            MERGE (p:Paper {id: $paper_id})
                            MERGE (p)-[:AUTHORED_BY]->(a)
                            """,
                            author=author_name.strip(), paper_id=paper_id,
                        )
                # Link concept categories
                for cat in (categories or []):
                    if cat.strip():
                        session.run(
                            """
                            MERGE (c:Concept {name: $cat})
                            SET c.type = 'category'
                            MERGE (p:Paper {id: $paper_id})
                            MERGE (p)-[:MENTIONS]->(c)
                            """,
                            cat=cat.strip(), paper_id=paper_id,
                        )
                return True
            except Exception as e:
                logger.error("Failed to upsert paper in graph", paper_id=paper_id, error=str(e))
                return False

    async def add_relation(
        self,
        source_id: str,
        source_label: str,
        target_id: str,
        target_label: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add an arbitrary typed relationship between two nodes."""
        if relation_type not in RELATION_TYPES:
            logger.warning("Unknown relation type", type=relation_type)
            return False

        props = properties or {}
        driver = self._get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            try:
                session.run(
                    f"""
                    MERGE (a:{source_label} {{id: $src_id}})
                    MERGE (b:{target_label} {{id: $tgt_id}})
                    MERGE (a)-[r:{relation_type}]->(b)
                    SET r += $props
                    """,
                    src_id=source_id, tgt_id=target_id, props=props,
                )
                return True
            except Exception as e:
                logger.error(
                    "Failed to add relation",
                    relation=relation_type, src=source_id, tgt=target_id, error=str(e),
                )
                return False

    async def link_extracted_entities(
        self,
        paper_id: str,
        entities: Dict[str, List[str]],
    ) -> bool:
        """
        Link extracted scientific entities to a paper in Neo4j.

        entities = {
            "methods": ["BERT", "SVM"],
            "datasets": ["ImageNet", "COCO"],
            "metrics": ["F1", "BLEU"],
            "diseases": ["cancer"],
            "drugs": ["aspirin"],
        }
        """
        driver = self._get_driver()
        label_map = {
            "methods": ("Method", "USES"),
            "datasets": ("Dataset", "USES"),
            "metrics": ("Metric", "MEASURED_BY"),
            "diseases": ("Disease", "STUDIES"),
            "drugs": ("Drug", "STUDIES"),
            "algorithms": ("Algorithm", "USES"),
            "concepts": ("Concept", "MENTIONS"),
        }

        with driver.session(database=settings.NEO4J_DATABASE) as session:
            try:
                for entity_type, (node_label, rel_type) in label_map.items():
                    for entity_name in entities.get(entity_type, []):
                        if not entity_name.strip():
                            continue
                        session.run(
                            f"""
                            MERGE (e:{node_label} {{name: $name}})
                            MERGE (p:Paper {{id: $paper_id}})
                            MERGE (p)-[:{rel_type}]->(e)
                            """,
                            name=entity_name.strip(), paper_id=paper_id,
                        )
                return True
            except Exception as e:
                logger.error("Failed to link entities", paper_id=paper_id, error=str(e))
                return False

    async def get_schema_summary(self) -> Dict[str, Any]:
        """Return counts of all node types and relationship types."""
        driver = self._get_driver()
        summary: Dict[str, Any] = {"nodes": {}, "relationships": {}}
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            for node_type in NODE_TYPES:
                try:
                    count = session.run(
                        f"MATCH (n:{node_type}) RETURN count(n) AS c"
                    ).single()["c"]
                    summary["nodes"][node_type] = count
                except Exception:
                    summary["nodes"][node_type] = 0

            for rel_type in RELATION_TYPES:
                try:
                    count = session.run(
                        f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS c"
                    ).single()["c"]
                    summary["relationships"][rel_type] = count
                except Exception:
                    summary["relationships"][rel_type] = 0

        return summary


# Singleton
graph_schema = GraphSchema()
