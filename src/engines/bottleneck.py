from typing import List, Dict, Any, Optional
from datetime import datetime
import inspect
import structlog
from ..bus import event_bus
from ..events import EventType
from ..models import Bottleneck
from ..memory.episodic import EpisodicMemory
from ..memory.semantic import SemanticMemory

logger = structlog.get_logger()

FIELD_CATEGORY_MAP: Dict[str, List[str]] = {
    "Cancer Research": ["cancer", "oncology", "tumor", "CRISPR", "Genome editing", "gene", "Transthyretin"],
    "Drug Discovery": ["drug", "pharma", "molecular", "compound", "discovery", "docking", "screening", "artificial intelligence"],
    "Gene Therapy": ["gene", "CRISPR", "Cas9", "genome", "genetic", "genomics", "editing", "nano"],
    "Quantum Computing": ["quantum", "qubit", "superposition", "entanglement", "NISQ", "photon"],
    "Materials Science": ["superconductiv", "materials", "hydride", "femtosecond", "graphene", "topological"],
    "AI/ML": ["machine learning", "deep learning", "neural", "transformer", "language model", "reinforcement", "vision", "robot"],
    "Genetics": ["genome", "gene", "CRISPR", "genetic", "genomics", "Cas9", "Ribonucleoprotein"],
    "Neuroscience": ["neural", "brain", "neuron", "spiking", "neuromorphic", "cognition", "memory"],
    "Physics": ["quantum", "superconductiv", "topological", "gravitational", "particle", "photon", "astrophysics"],
}


class BottleneckEngine:
    """Engine for detecting scientific bottlenecks."""
    
    def __init__(self):
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
    
    async def detect_bottlenecks(
        self,
        field: str,
        time_window_days: int = 10,
    ) -> List[Bottleneck]:
        """Detect bottlenecks in a scientific field using real papers."""
        bottlenecks = []

        # Get papers matching the field's category keywords
        category_keywords = FIELD_CATEGORY_MAP.get(field, [field.lower()])
        all_papers_result = self.episodic.list_papers(limit=100)
        all_papers = await all_papers_result if inspect.isawaitable(all_papers_result) else all_papers_result
        if not isinstance(all_papers, list):
            all_papers = []
        
        # Filter papers by category match
        matched_papers = []
        for paper in all_papers:
            payload = paper.get("payload", {})
            cats = [c.lower() for c in payload.get("categories", [])]
            title = payload.get("title", "").lower()
            abstract = payload.get("abstract", "").lower()
            combined = " ".join(cats) + " " + title + " " + abstract
            if any(kw.lower() in combined for kw in category_keywords):
                matched_papers.append(paper)
        
        # Also try embedding similarity search for broader coverage
        semantic_papers = await self.episodic.search_similar(
            await self._embed_query(f"{field} challenges limitations bottlenecks obstacles"),
            limit=50,
            filter_type="paper",
        )
        seen_ids = {p.get("id") for p in matched_papers}
        for p in semantic_papers:
            if p.get("id") not in seen_ids:
                matched_papers.append(p)
                seen_ids.add(p.get("id"))
        
        logger.info("Bottleneck analysis papers", field=field, matched=len(matched_papers))
        
        # Analyze papers with LLM first, fallback to keyword matching
        bottleneck_patterns = await self._analyze_with_llm(matched_papers, field)
        if not bottleneck_patterns:
            bottleneck_patterns = await self._identify_bottleneck_patterns(matched_papers)
        
        # Create bottleneck objects
        for pattern in bottleneck_patterns:
            bottleneck = Bottleneck(
                field=field,
                description=pattern["description"],
                major_bottleneck=pattern["major_bottleneck"],
                confidence=pattern["confidence"],
                evidence_papers=pattern.get("evidence_papers", []),
                suggested_approaches=pattern.get("suggested_approaches", []),
            )
            bottlenecks.append(bottleneck)
            await event_bus.bottleneck_found(bottleneck)
        
        logger.info(
            "Bottleneck detection completed",
            field=field,
            bottlenecks_found=len(bottlenecks),
        )
        
        return bottlenecks
    
    async def _embed_query(self, query: str):
        from ..services.embeddings import embedding_service
        return await embedding_service.embed_text(query)
    
    async def _analyze_with_llm(
        self, papers: List[Dict[str, Any]], field: str
    ) -> List[Dict[str, Any]]:
        """Use LLM to identify bottleneck patterns from papers."""
        if not papers:
            return []
        try:
            from ..services.llm import llm_service
            titles = [p.get("payload", {}).get("title", "") for p in papers[:8]]
            prompt = (
                f"Analyze these papers in '{field}' and identify key bottlenecks.\n\n"
                f"Papers:\n" + "\n".join(f"- {t}" for t in titles if t) +
                '\n\nReturn ONLY a valid JSON array, no other text. Example: '
                '[{"description": "short", "confidence": 0.7, "major_bottleneck": "name", '
                '"suggested_approaches": ["a"]}]. [] if none.'
            )
            result = await llm_service.generate(
                prompt,
                system_prompt="You are a research analyst. Return ONLY valid JSON arrays. Never include explanations.",
                temperature=0.3,
                max_tokens=2000,
            )
            import re as _re
            import json as _json
            cleaned = result.strip()
            # Strip markdown code fences
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                cleaned = cleaned.rsplit("```", 1)[0]
            # Extract JSON array from anywhere in the response
            match = _re.search(r'\[.*\]', cleaned, _re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in LLM response")
            parsed = _json.loads(match.group())
            if isinstance(parsed, list):
                for p in parsed:
                    p["evidence_papers"] = [pp.get("id") for pp in papers[:5]]
                    if "suggested_approaches" not in p:
                        p["suggested_approaches"] = ["Further investigation needed"]
                return parsed
        except Exception as e:
            logger.warning("LLM bottleneck analysis failed", error=str(e))
        return []
    
    async def _identify_bottleneck_patterns(
        self, papers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify bottleneck patterns from papers using keyword matching."""
        patterns = []
        
        bottleneck_keywords = {
            "challenge": 0.7,
            "limitation": 0.8,
            "barrier": 0.85,
            "obstacle": 0.85,
            "difficulty": 0.7,
            "problem": 0.6,
            "issue": 0.5,
            "gap": 0.75,
            "missing": 0.7,
            "lack": 0.7,
            "insufficient": 0.75,
            "inadequate": 0.75,
            "needs improvement": 0.8,
            "requires": 0.6,
        }
        
        for paper in papers:
            payload = paper.get("payload", {})
            abstract = payload.get("abstract", "").lower()
            title = payload.get("title", "").lower()
            
            combined_text = f"{title} {abstract}"
            
            for keyword, confidence in bottleneck_keywords.items():
                if keyword in combined_text:
                    patterns.append({
                        "description": f"Paper mentions '{keyword}' in context",
                        "major_bottleneck": self._extract_bottleneck_context(
                            combined_text, keyword
                        ),
                        "confidence": confidence,
                        "evidence_papers": [paper.get("id")],
                        "suggested_approaches": self._suggest_approaches(keyword),
                    })
        
        return self._deduplicate_patterns(patterns)
    
    def _extract_bottleneck_context(self, text: str, keyword: str) -> str:
        """Extract context around a bottleneck keyword."""
        words = text.split()
        keyword_idx = None
        
        for i, word in enumerate(words):
            if keyword in word:
                keyword_idx = i
                break
        
        if keyword_idx is None:
            return f"General {keyword} identified"
        
        start = max(0, keyword_idx - 5)
        end = min(len(words), keyword_idx + 10)
        
        return " ".join(words[start:end])
    
    def _suggest_approaches(self, bottleneck_type: str) -> List[str]:
        """Suggest approaches based on bottleneck type."""
        approaches = {
            "challenge": [
                "Review existing solutions",
                "Consider alternative methodologies",
                "Collaborate with domain experts",
            ],
            "limitation": [
                "Identify root causes",
                "Propose technical improvements",
                "Seek interdisciplinary solutions",
            ],
            "barrier": [
                "Analyze barrier components",
                "Develop incremental solutions",
                "Consider novel approaches",
            ],
            "gap": [
                "Conduct literature review",
                "Identify missing research",
                "Propose new experiments",
            ],
        }
        
        return approaches.get(bottleneck_type, [
            "Further investigation needed",
            "Expert consultation recommended",
        ])
    
    def _deduplicate_patterns(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate similar bottleneck patterns."""
        seen = set()
        unique_patterns = []
        
        for pattern in patterns:
            key = pattern["major_bottleneck"][:50]
            if key not in seen:
                seen.add(key)
                unique_patterns.append(pattern)
        
        return sorted(unique_patterns, key=lambda x: x["confidence"], reverse=True)
    
    async def get_bottleneck_summary(self, field: str) -> Dict[str, Any]:
        """Get a summary of bottlenecks in a field."""
        bottlenecks = await self.detect_bottlenecks(field)
        
        return {
            "field": field,
            "total_bottlenecks": len(bottlenecks),
            "high_confidence": len([b for b in bottlenecks if b.confidence > 0.8]),
            "medium_confidence": len([b for b in bottlenecks if 0.5 < b.confidence <= 0.8]),
            "low_confidence": len([b for b in bottlenecks if b.confidence <= 0.5]),
            "top_bottlenecks": [
                {
                    "description": b.description,
                    "confidence": b.confidence,
                }
                for b in bottlenecks[:5]
            ],
        }
