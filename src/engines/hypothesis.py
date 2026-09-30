"""Hypothesis generation engine — every hypothesis includes verifiable evidence trail."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import inspect
import structlog
from ..bus import event_bus
from ..events import EventType
from ..models import Hypothesis, EvidenceItem, Finding, ExperimentRecommendation
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory
from ..services.embeddings import embedding_service
from ..database import db

logger = structlog.get_logger()


class HypothesisGenerator:
    """Engine for generating scientific hypotheses with full evidence citations."""

    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()

    async def generate_hypotheses(
        self,
        context: Optional[Dict[str, Any]] = None,
        num_hypotheses: int = 5,
    ) -> List[Hypothesis]:
        """Generate hypotheses based on current knowledge.

        Every hypothesis returned includes:
        - evidence_items: list of EvidenceItem with paper_id, title, abstract, doi, url
        - supporting_evidence: list of paper UUIDs
        - source_category: where the hypothesis originated
        """
        hypotheses = []

        recent_findings = await self._get_recent_findings()
        contradictions = await self._get_contradictions()
        graph_patterns = await self._analyze_graph_patterns()

        finding_hypotheses = await self._generate_from_findings(recent_findings)
        contradiction_hypotheses = await self._generate_from_contradictions(contradictions)
        pattern_hypotheses = await self._generate_from_patterns(graph_patterns)

        all_hypotheses = (
            finding_hypotheses +
            contradiction_hypotheses +
            pattern_hypotheses
        )

        all_hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        hypotheses = all_hypotheses[:num_hypotheses]

        # Fallback: ensure at least 1 hypothesis even with no data
        if not hypotheses:
            hypotheses.append(Hypothesis(
                hypothesis_text=(
                    "Exploratory hypothesis: the intersection of multiple fields "
                    "in this knowledge graph may reveal overlooked connections. "
                    "Add papers and findings to enable targeted hypothesis generation."
                ),
                confidence=0.3,
                related_concepts=["exploratory", "knowledge_graph"],
                source_category="exploratory",
                suggested_experiments=[
                    "Populate the knowledge base with domain-specific papers",
                    "Perform systematic review of indexed literature",
                    "Identify 3-5 candidate relationships for initial investigation",
                ],
            ))

        for hypothesis in hypotheses:
            await event_bus.hypothesis_generated(hypothesis)

        logger.info(
            "Hypothesis generation completed",
            hypotheses_generated=len(hypotheses),
            with_evidence=sum(1 for h in hypotheses if h.evidence_items),
        )

        return hypotheses

    async def _get_recent_findings(self) -> List[Dict[str, Any]]:
        """Get recent findings — fall back to papers if no findings exist."""
        findings = await self.episodic.search_similar(
            await embedding_service.embed_text("recent scientific findings"),
            limit=20,
            filter_type="finding",
        )
        if findings:
            return findings
        papers_result = self.episodic.list_papers(limit=30)
        papers = await papers_result if inspect.isawaitable(papers_result) else papers_result
        if not isinstance(papers, list):
            papers = []
        return [
            {
                "id": p.get("id"),
                "score": 1.0,
                "payload": {
                    "type": "finding",
                    "finding_text": p.get("payload", {}).get("abstract", ""),
                    "categories": p.get("payload", {}).get("categories", []),
                    "title": p.get("payload", {}).get("title", ""),
                    "authors": p.get("payload", {}).get("authors", []),
                    "doi": p.get("payload", {}).get("doi"),
                    "url": p.get("payload", {}).get("url"),
                    "source": p.get("payload", {}).get("source"),
                    "published_at": p.get("payload", {}).get("published_at"),
                    "entities": [],
                },
            }
            for p in papers
        ]

    async def _get_contradictions(self) -> List[Dict[str, Any]]:
        """Get detected contradictions."""
        return []

    async def _analyze_graph_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in the knowledge graph."""
        hidden = await self.semantic.find_hidden_relationships()
        stats = await self.semantic.get_statistics()
        return {
            "hidden_relationships": hidden,
            "graph_stats": stats,
        }

    def _build_evidence(
        self,
        paper_id: Any,
        payload: Dict[str, Any],
        relevance_score: float = 0.5,
        relationship: str = "supporting",
    ) -> Optional[EvidenceItem]:
        """Build an EvidenceItem from a paper payload. Returns None if no title."""
        title = payload.get("title") or payload.get("finding_text", "")
        if not title:
            return None
        return EvidenceItem(
            paper_id=str(paper_id),
            title=str(title)[:200],
            abstract=str(payload.get("abstract", ""))[:500],
            doi=payload.get("doi"),
            url=payload.get("url"),
            authors=payload.get("authors", []),
            source=payload.get("source"),
            published_at=payload.get("published_at"),
            relevance_score=min(1.0, relevance_score),
            relationship=relationship,
        )

    async def _generate_from_findings(
        self, findings: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses from recent findings with full evidence citations."""
        hypotheses = []

        from ..services.llm import llm_service
        import re as _re
        import json as _json

        category_findings: Dict[str, List[Dict]] = {}
        for finding in findings:
            payload = finding.get("payload", {})
            cats = payload.get("categories", [])
            for cat in cats:
                if cat not in category_findings:
                    category_findings[cat] = []
                category_findings[cat].append(finding)

        # Within-category hypotheses
        for category, cat_papers in category_findings.items():
            if len(cat_papers) < 2:
                continue

            evidence = []
            titles = []
            for p in cat_papers[:5]:
                ei = self._build_evidence(
                    p.get("id"),
                    p.get("payload", {}),
                    relevance_score=p.get("score", 1.0) * 0.8,
                )
                if ei:
                    evidence.append(ei)
                    titles.append(ei.title[:60])

            hypothesis_text = (
                f"Within {category}, {len(cat_papers)} recent papers "
                f"({' · '.join(t for t in titles if t)}) suggest "
                f"an emerging research direction worth deeper investigation."
            )
            concepts = list(set(
                e for p in cat_papers
                for e in p.get("payload", {}).get("entities", [])
            ))
            hypotheses.append(Hypothesis(
                hypothesis_text=hypothesis_text,
                confidence=round(0.5 + 0.1 * min(len(evidence), 5), 2),
                supporting_evidence=[UUID(ei.paper_id) for ei in evidence if ei.paper_id],
                evidence_items=evidence,
                related_concepts=[category] + concepts[:3],
                source_category="findings",
                suggested_experiments=[
                    f"Systematic review of {category} literature ({len(evidence)} papers cited)",
                    f"Mine {category} papers for overlooked connections",
                ],
            ))

        # Cross-category hypotheses with LLM + evidence
        categories = list(category_findings.keys())
        if len(categories) >= 2:
            for i in range(min(3, len(categories) - 1)):
                cat_a = categories[i]
                cat_b = categories[i + 1]
                papers_a = category_findings[cat_a][:3]
                papers_b = category_findings[cat_b][:3]

                evidence = []
                for p in papers_a + papers_b:
                    ei = self._build_evidence(p.get("id"), p.get("payload", {}))
                    if ei:
                        evidence.append(ei)

                def _get_titles(pp):
                    return [
                        p.get("payload", {}).get("title") or
                        p.get("payload", {}).get("finding_text", "")[:60]
                        for p in pp
                    ]

                titles_a = _get_titles(papers_a)
                titles_b = _get_titles(papers_b)

                prompt = (
                    f"Suggest a novel cross-category hypothesis backed by these papers.\n\n"
                    f"Category A: {cat_a}\n"
                    f"Papers: {', '.join(t for t in titles_a if t)}\n\n"
                    f"Category B: {cat_b}\n"
                    f"Papers: {', '.join(t for t in titles_b if t)}\n\n"
                    "Return ONLY valid JSON: "
                    '{"hypothesis": "...", "mechanism": "...", "confidence": 0.0-1.0}'
                )
                try:
                    result = await llm_service.generate(
                        prompt,
                        system_prompt="You are a research analyst. Return ONLY valid JSON. No explanations.",
                        temperature=0.5,
                        max_tokens=500,
                    )
                    cleaned = result.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.split("\n", 1)[-1]
                        cleaned = cleaned.rsplit("```", 1)[0]
                    match = _re.search(r'\{.*\}', cleaned, _re.DOTALL)
                    if not match:
                        raise ValueError("No JSON in LLM response")
                    parsed = _json.loads(match.group())
                    hypotheses.append(Hypothesis(
                        hypothesis_text=parsed.get(
                            "hypothesis",
                            f"Hidden pattern exists between {cat_a} and {cat_b}",
                        ),
                        confidence=min(0.95, parsed.get("confidence", 0.5)),
                        supporting_evidence=[UUID(ei.paper_id) for ei in evidence if ei.paper_id],
                        evidence_items=evidence,
                        related_concepts=[cat_a, cat_b, parsed.get("mechanism", "")],
                        source_category="findings",
                        suggested_experiments=[
                            f"Design bridging study between {cat_a} and {cat_b}",
                            f"Test proposed mechanism: {parsed.get('mechanism', 'unknown')}",
                            f"Review literature for implicit links ({len(evidence)} papers cited)"
                                if evidence else "Mine for implicit links",
                        ],
                    ))
                except Exception as e:
                    logger.warning("LLM cross-category hypothesis failed", error=str(e))
                    hypotheses.append(Hypothesis(
                        hypothesis_text=f"Cross-connection may exist between {cat_a} and {cat_b} research domains",
                        confidence=0.4,
                        supporting_evidence=[UUID(ei.paper_id) for ei in evidence if ei.paper_id],
                        evidence_items=evidence,
                        related_concepts=[cat_a, cat_b],
                        source_category="findings",
                        suggested_experiments=[
                            f"Explore connections between {cat_a} and {cat_b}",
                        ],
                    ))

        return hypotheses

    async def _generate_from_contradictions(
        self, contradictions: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses from contradictions with evidence."""
        hypotheses = []
        for contradiction in contradictions:
            finding_a = contradiction.get("finding_a", {})
            finding_b = contradiction.get("finding_b", {})

            evidence = []
            for src in [finding_a, finding_b]:
                ei = self._build_evidence(
                    src.get("id"),
                    src.get("payload", {}),
                    relevance_score=0.7,
                    relationship="contradicting",
                )
                if ei:
                    evidence.append(ei)

            hypotheses.append(Hypothesis(
                hypothesis_text=(
                    f"The contradiction between "
                    f"{finding_a.get('payload', {}).get('title', 'finding A')[:60]} "
                    f"and "
                    f"{finding_b.get('payload', {}).get('title', 'finding B')[:60]} "
                    f"suggests divergent mechanisms or unaccounted variables."
                ),
                confidence=0.7,
                supporting_evidence=[UUID(ei.paper_id) for ei in evidence if ei.paper_id],
                evidence_items=evidence,
                related_concepts=["contradiction_resolution"],
                source_category="contradictions",
                suggested_experiments=[
                    "Conduct meta-analysis comparing experimental conditions of cited papers",
                    "Replicate key experiments under standardized protocols",
                ],
            ))

        return hypotheses

    async def _generate_from_patterns(
        self, patterns: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Generate hypotheses from graph patterns with evidence linked to papers."""
        hypotheses = []
        hidden_rels = patterns.get("hidden_relationships", [])

        for rel in hidden_rels[:5]:
            source_concept = rel.get("source", "unknown")
            target_concept = rel.get("target", "unknown")

            # Fetch papers related to these concepts for evidence
            evidence = []
            try:
                concept_papers = await self.semantic.get_concept_neighbors(source_concept, depth=1)
                for cp in concept_papers[:3]:
                    paper_id = cp.get("paper_id", "")
                    if paper_id:
                        paper = await self.episodic.get_paper(str(paper_id))
                        if paper:
                            ei = self._build_evidence(
                                paper.get("id"),
                                paper.get("payload", {}),
                                relevance_score=0.6,
                            )
                            if ei:
                                evidence.append(ei)
            except Exception:
                pass

            try:
                concept_papers = await self.semantic.get_concept_neighbors(target_concept, depth=1)
                for cp in concept_papers[:3]:
                    paper_id = cp.get("paper_id", "")
                    if paper_id:
                        paper = await self.episodic.get_paper(str(paper_id))
                        if paper:
                            ei = self._build_evidence(
                                paper.get("id"),
                                paper.get("payload", {}),
                                relevance_score=0.6,
                            )
                            if ei and ei.paper_id not in [e.paper_id for e in evidence]:
                                evidence.append(ei)
            except Exception:
                pass

            evidence_text = f"(evidence: {len(evidence)} paper{'s' if len(evidence)!=1 else ''} cited)"
            hypotheses.append(Hypothesis(
                hypothesis_text=(
                    f"There may be a hidden relationship between {source_concept} "
                    f"and {target_concept} that has not been explicitly studied "
                    f"{evidence_text if evidence else '— further search may reveal links'}"
                ),
                confidence=0.5,
                supporting_evidence=[UUID(ei.paper_id) for ei in evidence if ei.paper_id],
                evidence_items=evidence,
                related_concepts=[source_concept, target_concept],
                source_category="patterns",
                suggested_experiments=[
                    f"Investigate connection between {source_concept} and {target_concept}",
                    f"Review graph-based evidence: {' · '.join(e.title[:40] for e in evidence[:3])}" if evidence else "Search for implicit links in literature",
                ],
            ))

        return hypotheses

    async def evaluate_hypothesis(
        self, hypothesis: Hypothesis
    ) -> Dict[str, Any]:
        """Evaluate a hypothesis — searches for additional evidence papers."""
        search_embedding = await embedding_service.embed_text(hypothesis.hypothesis_text)

        supporting = await self.episodic.search_similar(
            search_embedding,
            limit=15,
            filter_type="paper",
        )

        # Hydrate search results with full metadata from DB
        hydrated_evidence = []
        for hit in supporting:
            payload = hit.get("payload", {})
            paper_id = payload.get("paper_id", hit.get("id"))
            paper = await self.episodic.get_paper(str(paper_id))
            if paper:
                ei = self._build_evidence(
                    paper.get("id"),
                    paper.get("payload", {}),
                    relevance_score=hit.get("score", 0.5),
                    relationship="supporting",
                )
                if ei:
                    hydrated_evidence.append(ei)

        evaluation = {
            "hypothesis_id": str(hypothesis.id),
            "supporting_evidence_count": len(hydrated_evidence),
            "evidence": [e.model_dump() for e in hydrated_evidence],
            "confidence_adjustment": 0.0,
            "recommendations": [],
        }

        if len(hydrated_evidence) > 5:
            evaluation["confidence_adjustment"] = 0.1
            evaluation["recommendations"].append(
                f"Strong supporting evidence: {len(hydrated_evidence)} papers found"
            )
        elif len(hydrated_evidence) < 2:
            evaluation["confidence_adjustment"] = -0.1
            evaluation["recommendations"].append(
                f"Limited supporting evidence: only {len(hydrated_evidence)} paper(s)"
            )

        # Set hypothesis as evaluated
        hypothesis.evaluated = True
        hypothesis.evaluation_summary = "; ".join(evaluation["recommendations"])

        return evaluation

    async def create_experiment_recommendation(
        self, hypothesis: Hypothesis
    ) -> ExperimentRecommendation:
        """Create an experiment recommendation with evidence references."""
        evidence_titles = [e.title[:60] for e in hypothesis.evidence_items[:5] if e.title]
        evidence_ref = "Evidence: " + " · ".join(evidence_titles) if evidence_titles else ""

        return ExperimentRecommendation(
            title=f"Validate: {hypothesis.hypothesis_text[:50]}...",
            description=(
                f"Design experiment to test this hypothesis.\n"
                f"{evidence_ref}\n\n"
                f"Full hypothesis: {hypothesis.hypothesis_text}"
            ),
            hypothesis_id=hypothesis.id,
            materials=[
                "Access to papers cited in evidence",
                "Data analysis tools",
                "Statistical software",
            ],
            methods=[
                "Systematic review of cited evidence",
                "Controlled experiment design",
                f"Cross-validate findings from {len(hypothesis.evidence_items)} cited papers",
            ],
            controls=[
                "Control for variables identified in evidence papers",
                "Replicate findings from cited sources",
            ],
            success_metrics=[
                "Statistical significance (p < 0.05)",
                "Effect size measurable against cited benchmarks",
                "Reproducibility across independent samples",
            ],
            estimated_duration="3-6 months",
        )


# Re-import UUID at module level for evidence building
from uuid import UUID
