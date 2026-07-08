from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import re
import structlog
from ..bus import event_bus
from ..events import EventType
from ..models import Finding, Contradiction
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory
from ..services.embeddings import embedding_service
from ..services.llm import llm_service

logger = structlog.get_logger()

CONTRADICTION_SYSTEM_PROMPT = """
You are a scientific fact-checking specialist. You analyze pairs of scientific findings.
Return ONLY valid JSON with this exact structure:
{
  "contradicts": true or false,
  "contradiction_type": one of ["direct_negation", "methodological_conflict", "scope_mismatch", "temporal_conflict", "population_conflict", "dosage_conflict", "none"],
  "confidence": a float between 0.0 and 1.0,
  "explanation": "1-2 sentence explanation of why these findings do or don't contradict",
  "resolution_suggestions": ["suggestion 1", "suggestion 2"]
}
Rules: Be precise. Only flag real contradictions, not just different topics.
"""


class ContradictionEngine:
    """Engine for detecting contradictions between scientific findings."""
    
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
    
    async def detect_contradictions(
        self,
        findings: List[Finding],
        similarity_threshold: float = 0.8,
    ) -> List[Contradiction]:
        """Detect contradictions between findings."""
        contradictions = []
        
        # Generate embeddings for all findings
        embeddings = []
        for finding in findings:
            embedding = await embedding_service.embed_finding(finding.finding_text)
            embeddings.append((finding, embedding))
        
        # Compare findings pairwise (optimized with batching)
        for i in range(len(embeddings)):
            finding_a, embedding_a = embeddings[i]
            
            # Find similar findings
            similar_findings = await self.episodic.search_similar(
                embedding_a,
                limit=10,
                filter_type="finding",
            )
            
            for result in similar_findings:
                finding_b_id = result["id"]
                similarity = result["score"]
                
                # Skip if too similar (likely same finding)
                if similarity > similarity_threshold:
                    continue
                
                # Find the actual finding
                finding_b = next(
                    (f for f, _ in embeddings if str(f.id) == finding_b_id),
                    None,
                )
                
                if finding_b and finding_a.id != finding_b.id:
                    # Check for contradiction
                    contradiction = await self._analyze_contradiction(
                        finding_a,
                        finding_b,
                        similarity,
                    )
                    
                    if contradiction:
                        contradictions.append(contradiction)
                        await event_bus.contradiction_detected(contradiction)
        
        logger.info(
            "Contradiction detection completed",
            findings_analyzed=len(findings),
            contradictions_found=len(contradictions),
        )
        
        return contradictions
    
    async def _analyze_contradiction(
        self,
        finding_a: Finding,
        finding_b: Finding,
        similarity: float,
    ) -> Optional[Contradiction]:
        """Analyze if two findings contradict each other using LLM."""
        text_a = finding_a.finding_text
        text_b = finding_b.finding_text

        # Quick pre-filter: only send semantically similar texts to LLM
        # (similarity too high = same claim, too low = unrelated)
        if similarity > 0.95 or similarity < 0.3:
            return None

        prompt = (
            f"Finding A:\n{text_a[:600]}\n\n"
            f"Finding B:\n{text_b[:600]}\n\n"
            "Do these two scientific findings contradict each other?"
        )

        try:
            result = await llm_service.generate(
                prompt=prompt,
                system_prompt=CONTRADICTION_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=400,
            )
            parsed = self._parse_llm_result(result)
            if not parsed or not parsed.get("contradicts"):
                return None

            confidence = float(parsed.get("confidence", 0.5))
            if confidence < 0.5:
                return None

            return Contradiction(
                finding_a_id=finding_a.id,
                finding_b_id=finding_b.id,
                contradiction_type=parsed.get("contradiction_type", "direct_negation"),
                explanation=parsed.get("explanation", "LLM detected contradiction"),
                confidence=min(0.95, confidence),
                resolution_suggestions=parsed.get("resolution_suggestions", [
                    "Replicate both experiments under standardized conditions",
                    "Conduct meta-analysis to reconcile findings",
                ]),
            )
        except Exception as e:
            logger.warning("LLM contradiction analysis failed, skipping", error=str(e))
            return None

    def _parse_llm_result(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    
    async def analyze_contradiction_context(
        self,
        contradiction: Contradiction,
    ) -> Dict[str, Any]:
        """Analyze the context of a contradiction for resolution."""
        # Get the findings
        finding_a = await self.episodic.get_paper(str(contradiction.finding_a_id))
        finding_b = await self.episodic.get_paper(str(contradiction.finding_b_id))
        
        context = {
            "contradiction_id": str(contradiction.id),
            "finding_a": finding_a,
            "finding_b": finding_b,
            "analysis": {
                "sample_size_comparison": "pending",
                "methodology_comparison": "pending",
                "temporal_analysis": "pending",
                "demographic_analysis": "pending",
            },
            "recommendations": [
                "Conduct meta-analysis with larger sample",
                "Replicate experiments under standardized conditions",
                "Review and standardize methodologies",
                "Consider publishing combined analysis",
            ],
        }
        
        return context
    
    async def get_contradiction_summary(self) -> Dict[str, Any]:
        """Get a summary of all detected contradictions from the knowledge graph."""
        from neo4j import GraphDatabase
        from ..config import settings as _settings
        driver = GraphDatabase.driver(
            _settings.NEO4J_URI,
            auth=(_settings.NEO4J_USER, _settings.NEO4J_PASSWORD),
        )
        summary = {
            "total_contradictions": 0,
            "by_type": {},
            "high_confidence": 0,
            "resolution_pending": 0,
        }
        try:
            with driver.session(database=_settings.NEO4J_DATABASE) as session:
                count = session.run(
                    "MATCH ()-[r:CONTRADICTS]->() RETURN count(r) AS c"
                ).single()["c"]
                summary["total_contradictions"] = count
        except Exception:
            pass
        finally:
            driver.close()
        return summary
