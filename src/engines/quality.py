"""Quality pipeline: coordinates validation, dedup, provenance, enrichment, and storage."""

from typing import Dict, Any, Optional, Tuple
import numpy as np
import structlog
from .dedup import DedupEngine
from ..services.validator import validate_paper, score_paper_quality, enrich_paper
from ..memory.provenance import build_provenance, mark_validated, mark_duplicate, merge_provenance
from ..memory.episodic import EpisodicMemory

logger = structlog.get_logger()

MIN_QUALITY_SCORE = 0.3


class QualityPipeline:
    """Orchestrates the full data quality pipeline for paper ingestion."""

    def __init__(self):
        self.dedup = DedupEngine()
        self.episodic = EpisodicMemory()

    async def process_paper(
        self,
        paper: Dict[str, Any],
        embedding: np.ndarray,
        source: str = "unknown",
        source_id: str = "",
        skip_quality_filter: bool = False,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Process a paper through the full quality pipeline.

        Steps:
        1. Build provenance
        2. Enrich missing fields
        3. Validate
        4. Score quality
        5. Check for duplicates
        6. Store or merge

        Returns: (accepted, result_or_none, message)
        """
        paper_id = paper.get("id", "unknown")
        logger.info("Processing paper through quality pipeline", paper_id=paper_id)

        # Step 1: Build provenance
        provenance = build_provenance(source, source_id)
        paper["provenance"] = provenance

        # Step 2: Enrich missing fields
        paper = enrich_paper(paper)
        paper["source"] = source.lower()

        # Step 3: Validate
        is_valid, errors = validate_paper(paper)
        provenance = mark_validated(provenance, errors)

        if not is_valid and not skip_quality_filter:
            logger.warning("Paper failed validation", paper_id=paper_id, errors=errors)
            return False, paper, f"Validation failed: {'; '.join(errors)}"

        # Step 4: Score quality
        quality_score = score_paper_quality(paper)
        provenance["quality_score"] = quality_score
        paper["provenance"] = provenance
        paper["quality_score"] = quality_score

        if quality_score < MIN_QUALITY_SCORE and not skip_quality_filter:
            logger.warning("Paper below quality threshold", paper_id=paper_id, score=quality_score)
            return False, paper, f"Quality score {quality_score:.2f} below minimum {MIN_QUALITY_SCORE}"

        # Step 5: Check for duplicates
        duplicate = await self.dedup.find_duplicate(paper)
        if duplicate:
            return await self._handle_duplicate(paper, duplicate, embedding)

        # Step 6: Store new paper
        return await self._store_new(paper, embedding)

    async def _handle_duplicate(
        self,
        paper: Dict[str, Any],
        duplicate: Dict[str, Any],
        embedding: np.ndarray,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Handle a duplicate by merging into the existing paper."""
        provenance = mark_duplicate(paper["provenance"], str(duplicate.get("id", "")))
        paper["provenance"] = provenance

        merged = await self.dedup.merge_papers(duplicate, paper)
        merged_payload = merged.get("payload", {})
        merged_id = str(merged.get("id", ""))

        await self.episodic.update_paper(merged_id, merged_payload)

        logger.info("Merged duplicate paper", incoming_id=paper.get("id"), into=merged_id)
        return False, merged, f"Merged duplicate into {merged_id}"

    async def _store_new(
        self,
        paper: Dict[str, Any],
        embedding: np.ndarray,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Store a new (non-duplicate) paper."""
        try:
            stored_id = await self.episodic.store_paper(paper, embedding)
            paper["id"] = stored_id
            logger.info("Paper stored after quality pipeline", paper_id=stored_id)
            return True, paper, "Paper accepted and stored"
        except Exception as e:
            logger.error("Failed to store paper", paper_id=paper.get("id"), error=str(e))
            return False, paper, f"Storage failed: {str(e)}"

    async def batch_process(
        self,
        papers: list[Dict[str, Any]],
        get_embedding_fn,
        source: str = "unknown",
        skip_quality_filter: bool = False,
    ) -> Dict[str, Any]:
        """Process multiple papers in batch.

        Args:
            papers: list of paper dicts
            get_embedding_fn: async callable(paper_dict) -> np.ndarray
        """
        accepted = 0
        rejected = 0
        merged = 0
        errors = 0
        results: list[Dict[str, Any]] = []

        for paper in papers:
            try:
                embedding = await get_embedding_fn(paper)
                ok, result, msg = await self.process_paper(
                    paper,
                    embedding=embedding,
                    source=source,
                    source_id=paper.get("id", ""),
                    skip_quality_filter=skip_quality_filter,
                )
                if ok:
                    accepted += 1
                elif "Merged" in msg:
                    merged += 1
                else:
                    rejected += 1
                results.append({"accepted": ok, "message": msg})
            except Exception as e:
                errors += 1
                results.append({"accepted": False, "message": str(e)})
                logger.error("Batch processing error", error=str(e))

        summary = {
            "total": len(papers),
            "accepted": accepted,
            "rejected": rejected,
            "merged": merged,
            "errors": errors,
        }
        logger.info("Batch processing complete", **summary)
        return summary, results
