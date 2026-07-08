"""
Scientific Information Extraction Engine.

Uses LLM (Groq → Ollama → HuggingFace) to extract structured scientific
entities from paper abstracts:

  Problem, Method, Dataset, Algorithm, Evaluation Metric, Result,
  Future Work, Limitation, Claim, Evidence, Disease, Drug, Protein

Extracted entities are stored in Neo4j via graph_schema.link_extracted_entities().
"""

from typing import List, Dict, Any, Optional
import json
import re
import structlog
from ..services.llm import llm_service
from ..memory.graph_schema import graph_schema
from ..bus import event_bus
from ..events import EventType, Event

logger = structlog.get_logger()


EXTRACTION_SYSTEM_PROMPT = """You are a scientific information extraction specialist.
Extract structured entities from the paper abstract provided.

Return ONLY a valid JSON object with these keys (all arrays of strings):
{
  "problem": ["the main problem being solved"],
  "methods": ["methods/approaches used, e.g. BERT, CNN, SVM"],
  "datasets": ["datasets used, e.g. ImageNet, MIMIC-III"],
  "algorithms": ["specific algorithms, e.g. Adam optimizer, Random Forest"],
  "metrics": ["evaluation metrics, e.g. F1 score, BLEU, AUC"],
  "results": ["key quantitative results, e.g. 94.2% accuracy"],
  "future_work": ["suggested future directions"],
  "limitations": ["limitations mentioned"],
  "claims": ["main claims/contributions of the paper"],
  "diseases": ["disease names if biomedical paper, else []"],
  "drugs": ["drug names if biomedical paper, else []"],
  "proteins": ["protein/gene names if biomedical, else []"],
  "concepts": ["key scientific concepts not covered above"]
}

Rules:
- Be specific and concise. Each array item should be a short phrase.
- Use empty arrays [] if a category has no relevant content.
- Do NOT include filler text. Only real extracted entities.
- Return ONLY the JSON, no explanation."""


class ScientificExtractor:
    """Extracts structured scientific entities from paper text using LLM."""

    async def extract_from_paper(
        self,
        paper_id: str,
        title: str,
        abstract: str,
        store_in_graph: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract entities from a paper and optionally store them in Neo4j.

        Returns the extracted entity dict.
        """
        if not abstract and not title:
            return {}

        text = f"Title: {title}\n\nAbstract: {abstract}"
        entities = await self._extract_entities(text)

        if entities and store_in_graph:
            await graph_schema.link_extracted_entities(paper_id, entities)
            await event_bus.publish(Event(
                type=EventType.PAPER_INDEXED,
                data={
                    "paper_id": paper_id,
                    "title": title[:60],
                    "entities_extracted": sum(len(v) for v in entities.values()),
                    "methods": entities.get("methods", [])[:3],
                    "datasets": entities.get("datasets", [])[:3],
                },
                room="pipeline",
            ))
            logger.info(
                "Entities extracted and stored",
                paper_id=paper_id,
                methods=len(entities.get("methods", [])),
                datasets=len(entities.get("datasets", [])),
                diseases=len(entities.get("diseases", [])),
            )

        return entities

    async def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Run LLM extraction and parse result."""
        prompt = f"Extract scientific entities from this paper:\n\n{text[:2000]}"
        try:
            result = await llm_service.generate(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1000,
            )
            return self._parse_json(result)
        except Exception as e:
            logger.error("LLM extraction failed", error=str(e))
            return {}

    def _parse_json(self, raw: str) -> Dict[str, List[str]]:
        """Robustly parse LLM JSON output."""
        cleaned = raw.strip()
        # Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        # Extract JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group())
            # Normalize: ensure all values are lists of strings
            result = {}
            expected_keys = [
                "problem", "methods", "datasets", "algorithms", "metrics",
                "results", "future_work", "limitations", "claims",
                "diseases", "drugs", "proteins", "concepts",
            ]
            for key in expected_keys:
                val = parsed.get(key, [])
                if isinstance(val, list):
                    result[key] = [str(v) for v in val if v]
                elif isinstance(val, str) and val:
                    result[key] = [val]
                else:
                    result[key] = []
            return result
        except json.JSONDecodeError:
            return {}

    async def batch_extract(
        self,
        papers: List[Dict[str, Any]],
        store_in_graph: bool = True,
    ) -> List[Dict[str, Any]]:
        """Extract entities from multiple papers."""
        results = []
        for paper in papers:
            paper_id = str(paper.get("id", ""))
            title = paper.get("title", "")
            abstract = paper.get("abstract", "") or ""
            if not paper_id or not (title or abstract):
                continue
            entities = await self.extract_from_paper(
                paper_id=paper_id,
                title=title,
                abstract=abstract,
                store_in_graph=store_in_graph,
            )
            results.append({
                "paper_id": paper_id,
                "title": title[:60],
                "entities": entities,
            })
        return results

    async def extract_claim_evidence_pairs(
        self, paper_id: str, title: str, abstract: str
    ) -> List[Dict[str, str]]:
        """Extract explicit claim-evidence pairs from a paper."""
        prompt = (
            f"From this paper abstract, extract all explicit CLAIM → EVIDENCE pairs.\n\n"
            f"Title: {title}\nAbstract: {abstract[:1500]}\n\n"
            "Return JSON array: [{\"claim\": \"...\", \"evidence\": \"...\"}]\n"
            "Return ONLY the JSON array."
        )
        try:
            result = await llm_service.generate(prompt, temperature=0.1, max_tokens=800)
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:-1])
            match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if match:
                pairs = json.loads(match.group())
                return pairs if isinstance(pairs, list) else []
        except Exception as e:
            logger.warning("Claim-evidence extraction failed", error=str(e))
        return []


# Singleton
scientific_extractor = ScientificExtractor()
