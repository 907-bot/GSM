"""
Novelty Engine — the heart of the Autonomous Scientific Discovery Platform.

Detects:
1. Unexplored concept combinations ("what has nobody tried yet")
2. Drug → Protein → Disease link predictions (drug repurposing)
3. Novelty scoring for a proposed concept combination
4. Community detection (concept clusters)
5. Temporal trend analysis (rising concepts)
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import structlog
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..services.llm import llm_service
from ..bus import event_bus
from ..events import EventType, Event
from ..config import settings

logger = structlog.get_logger()


class NoveltyEngine:
    """
    Detects research gaps, scores novelty of proposed ideas, and surfaces
    unexplored concept combinations from the knowledge graph.
    """

    def __init__(self):
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Unexplored Concept Combinations
    # ──────────────────────────────────────────────────────────────────────────

    async def find_unexplored_combinations(
        self,
        min_confidence: float = 0.3,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Detect concept pairs that have indirect connections (path length ≥ 2)
        but NO direct paper linking them.

        This is the "what has nobody tried yet" detector.
        """
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

        combinations = []
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Find concept pairs connected via intermediate concept but no direct paper
            result = session.run("""
                MATCH (a:Concept)-[:MENTIONS|USES|STUDIES*1..2]-(bridge)-[:MENTIONS|USES|STUDIES*1..2]-(b:Concept)
                WHERE a <> b
                  AND a.name < b.name
                  AND NOT EXISTS {
                      MATCH (p:Paper)-[:MENTIONS|USES]->(a)
                      MATCH (p)-[:MENTIONS|USES]->(b)
                  }
                WITH a, b, count(bridge) AS bridge_strength
                WHERE bridge_strength >= 2
                RETURN a.name AS concept_a,
                       b.name AS concept_b,
                       bridge_strength,
                       bridge_strength * 1.0 / (bridge_strength + 5) AS confidence
                ORDER BY confidence DESC
                LIMIT $limit
            """, limit=max_results * 3)

            for record in result:
                conf = float(record["confidence"])
                if conf >= min_confidence:
                    combinations.append({
                        "concept_a": record["concept_a"],
                        "concept_b": record["concept_b"],
                        "bridge_strength": record["bridge_strength"],
                        "confidence": round(conf, 3),
                        "novelty_type": "unexplored_combination",
                        "recommendation": (
                            f"No paper has directly combined '{record['concept_a']}' "
                            f"and '{record['concept_b']}' — {record['bridge_strength']} "
                            f"intermediate connections suggest high potential."
                        ),
                    })

        driver.close()

        # Enrich top 10 with LLM-generated research question
        enriched = []
        for combo in combinations[:10]:
            combo["research_question"] = await self._generate_research_question(
                combo["concept_a"], combo["concept_b"]
            )
            enriched.append(combo)
        enriched.extend(combinations[10:max_results])

        for combo in enriched[:5]:
            await event_bus.publish(Event(
                type=EventType.GRAPH_CLUSTER_DETECTED,
                data={"type": "missing_combination", **combo},
                room="discovery",
            ))

        logger.info("Unexplored combinations found", count=len(enriched))
        return enriched[:max_results]

    async def _generate_research_question(
        self, concept_a: str, concept_b: str
    ) -> str:
        """Use LLM to generate a specific research question for a gap."""
        prompt = (
            f"The combination of '{concept_a}' and '{concept_b}' has NOT been "
            f"directly studied in existing literature. "
            f"Write ONE specific, actionable research question that could bridge these two concepts. "
            f"Keep it under 2 sentences."
        )
        try:
            result = await llm_service.generate(
                prompt, temperature=0.6, max_tokens=150
            )
            return result.strip()
        except Exception:
            return f"How can {concept_a} be applied to or combined with {concept_b}?"

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Drug Repurposing / Disease Link Prediction
    # ──────────────────────────────────────────────────────────────────────────

    async def find_drug_repurposing_candidates(
        self, max_results: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Detect Drug → Protein → Disease chains where no direct Drug → Disease
        paper exists. Classic drug repurposing pattern.
        """
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

        candidates = []
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (drug:Drug)-[:TARGETS|STUDIES]->(protein:Protein|Concept)
                      -[:ASSOCIATED_WITH|STUDIES]->(disease:Disease)
                WHERE NOT EXISTS {
                    MATCH (p:Paper)-[:STUDIES]->(drug)
                    MATCH (p)-[:STUDIES]->(disease)
                }
                RETURN drug.name AS drug,
                       protein.name AS protein,
                       disease.name AS disease,
                       count(*) AS evidence_strength
                ORDER BY evidence_strength DESC
                LIMIT $limit
            """, limit=max_results)

            for record in result:
                candidates.append({
                    "drug": record["drug"],
                    "protein": record["protein"],
                    "disease": record["disease"],
                    "evidence_strength": record["evidence_strength"],
                    "hypothesis": (
                        f"{record['drug']} targets {record['protein']}, which is "
                        f"associated with {record['disease']} — suggesting "
                        f"{record['drug']} may have therapeutic potential for "
                        f"{record['disease']}."
                    ),
                    "novelty_type": "drug_repurposing",
                })

        driver.close()
        logger.info("Drug repurposing candidates found", count=len(candidates))
        return candidates

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Novelty Scoring
    # ──────────────────────────────────────────────────────────────────────────

    async def score_novelty(
        self, concepts: List[str]
    ) -> Dict[str, Any]:
        """
        Score how novel a concept combination is (0 = well-studied, 1 = completely novel).

        Score = 1 - (existing_papers_combining_all / max_papers_per_concept)
        """
        if not concepts:
            return {"novelty_score": 0.0, "explanation": "No concepts provided"}

        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

        concept_paper_counts: Dict[str, int] = {}
        combo_paper_count = 0

        with driver.session(database=settings.NEO4J_DATABASE) as session:
            # Count papers per concept
            for concept in concepts:
                result = session.run(
                    """
                    MATCH (p:Paper)-[:MENTIONS|USES|STUDIES]->(c)
                    WHERE c.name = $name
                    RETURN count(p) AS c
                    """,
                    name=concept,
                )
                record = result.single()
                concept_paper_counts[concept] = record["c"] if record else 0

            # Count papers combining ALL concepts
            if len(concepts) >= 2:
                # Build a chain of MATCH clauses
                match_clauses = []
                params: Dict[str, Any] = {}
                for i, concept in enumerate(concepts):
                    params[f"c{i}"] = concept
                    match_clauses.append(
                        f"MATCH (p)-[:MENTIONS|USES|STUDIES]->(n{i}) WHERE n{i}.name = $c{i}"
                    )

                cypher = "MATCH (p:Paper)\n" + "\n".join(match_clauses) + "\nRETURN count(p) AS c"
                try:
                    result = session.run(cypher, **params)
                    record = result.single()
                    combo_paper_count = record["c"] if record else 0
                except Exception as e:
                    logger.warning("Combo count query failed", error=str(e))
                    combo_paper_count = 0
            else:
                combo_paper_count = concept_paper_counts.get(concepts[0], 0)

        driver.close()

        max_individual = max(concept_paper_counts.values()) if concept_paper_counts else 0
        if max_individual == 0:
            novelty_score = 1.0
            explanation = "None of these concepts appear in the knowledge graph — completely unexplored territory."
        elif combo_paper_count == 0:
            novelty_score = 0.9
            explanation = (
                f"Individual concepts are studied ({max_individual} papers for most common), "
                f"but no paper combines all {len(concepts)} concepts. High novelty."
            )
        else:
            ratio = combo_paper_count / max(1, max_individual)
            novelty_score = round(max(0.0, 1.0 - ratio), 3)
            explanation = (
                f"{combo_paper_count} paper(s) already combine these concepts "
                f"(vs {max_individual} papers for the most common concept). "
                f"Novelty score: {novelty_score:.0%}."
            )

        return {
            "concepts": concepts,
            "novelty_score": novelty_score,
            "combo_paper_count": combo_paper_count,
            "individual_counts": concept_paper_counts,
            "explanation": explanation,
            "verdict": (
                "Highly novel" if novelty_score >= 0.8 else
                "Moderately novel" if novelty_score >= 0.5 else
                "Low novelty (well-studied)"
            ),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Community Detection (Rising Concepts)
    # ──────────────────────────────────────────────────────────────────────────

    async def detect_rising_concepts(
        self,
        time_window_days: int = 30,
        min_papers: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Detect concepts that are rising in frequency over the past N days
        compared to the period before that.
        """
        recent_papers = await self.episodic.get_recent_papers(limit=500)
        now = datetime.now()
        cutoff = now - timedelta(days=time_window_days)
        earlier_cutoff = cutoff - timedelta(days=time_window_days)

        recent_counts: Dict[str, int] = {}
        earlier_counts: Dict[str, int] = {}

        for paper in recent_papers:
            payload = paper.get("payload", {})
            cats = payload.get("categories", [])
            pub_str = payload.get("published_at", "")

            try:
                pub_date = datetime.fromisoformat(str(pub_str)[:10]) if pub_str else None
            except (ValueError, TypeError):
                pub_date = None

            for cat in cats:
                if not cat:
                    continue
                if pub_date and pub_date >= cutoff:
                    recent_counts[cat] = recent_counts.get(cat, 0) + 1
                elif pub_date and pub_date >= earlier_cutoff:
                    earlier_counts[cat] = earlier_counts.get(cat, 0) + 1

        rising = []
        for concept, recent in recent_counts.items():
            if recent < min_papers:
                continue
            earlier = earlier_counts.get(concept, 0)
            growth = (recent - earlier) / max(1, earlier)
            if growth > 0.2 or (earlier == 0 and recent >= min_papers):
                rising.append({
                    "concept": concept,
                    "recent_count": recent,
                    "earlier_count": earlier,
                    "growth_rate": round(growth, 3),
                    "trend": "emerging" if earlier == 0 else "rising",
                })

        rising.sort(key=lambda x: x["growth_rate"], reverse=True)
        return rising[:20]

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Three-hop Hypothesis Generation
    # ──────────────────────────────────────────────────────────────────────────

    async def find_three_hop_hypotheses(
        self, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find A → B, B → C, but no direct A → C paper.
        These are prime hypothesis candidates.
        """
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )

        hypotheses = []
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (a)-[:MENTIONS|USES|STUDIES]->(bridge)-[:MENTIONS|USES|STUDIES]->(c)
                WHERE a <> c
                  AND NOT EXISTS {
                      MATCH (p:Paper)
                      MATCH (p)-[:MENTIONS|USES|STUDIES]->(a)
                      MATCH (p)-[:MENTIONS|USES|STUDIES]->(c)
                  }
                WITH a, bridge, c, count(*) AS strength
                WHERE strength >= 2
                RETURN a.name AS node_a,
                       bridge.name AS bridge_node,
                       c.name AS node_c,
                       strength
                ORDER BY strength DESC
                LIMIT $limit
            """, limit=max_results * 2)

            for record in result:
                hypotheses.append({
                    "node_a": record["node_a"],
                    "bridge": record["bridge_node"],
                    "node_c": record["node_c"],
                    "strength": record["strength"],
                    "hypothesis": (
                        f"'{record['node_a']}' connects to '{record['bridge_node']}', "
                        f"which connects to '{record['node_c']}', but no paper "
                        f"directly studies '{record['node_a']}' + '{record['node_c']}'. "
                        f"This is a high-potential research gap."
                    ),
                    "novelty_type": "three_hop_gap",
                })

        driver.close()
        return hypotheses[:max_results]


# Singleton
novelty_engine = NoveltyEngine()
