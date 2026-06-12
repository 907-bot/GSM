from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from ..bus import event_bus
from ..events import EventType
from ..models import Finding, Contradiction
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory
from ..services.embeddings import embedding_service

logger = structlog.get_logger()


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
        """Analyze if two findings contradict each other."""
        # Simple heuristic-based contradiction detection
        # In production, this would use LLM for nuanced analysis
        
        contradiction_indicators = [
            # Direct negation
            ("works", "fails"),
            ("effective", "ineffective"),
            ("increases", "decreases"),
            ("positive", "negative"),
            ("significant", "insignificant"),
            ("correlation", "no correlation"),
            ("cause", "no cause"),
            ("supports", "contradicts"),
            ("beneficial", "harmful"),
            ("improves", "worsens"),
        ]
        
        text_a = finding_a.finding_text.lower()
        text_b = finding_b.finding_text.lower()
        
        # Check for contradictory terms
        for term_a, term_b in contradiction_indicators:
            if (term_a in text_a and term_b in text_b) or \
               (term_b in text_a and term_a in text_b):
                
                # Calculate confidence based on similarity and specificity
                confidence = min(0.9, max(0.5, 1.0 - similarity))
                
                return Contradiction(
                    finding_a_id=finding_a.id,
                    finding_b_id=finding_b.id,
                    contradiction_type="direct_contradiction",
                    explanation=f"Findings contain contradictory terms: '{term_a}' vs '{term_b}'",
                    confidence=confidence,
                    resolution_suggestions=[
                        "Check sample sizes and demographics",
                        "Compare experimental conditions",
                        "Review methodology differences",
                        "Consider temporal factors",
                    ],
                )
        
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
        """Get a summary of all detected contradictions."""
        # This would query the database for all contradictions
        # For now, return a placeholder
        
        return {
            "total_contradictions": 0,
            "by_type": {
                "direct_contradiction": 0,
                "methodological_difference": 0,
                "temporal_difference": 0,
            },
            "high_confidence": 0,
            "resolution_pending": 0,
        }
