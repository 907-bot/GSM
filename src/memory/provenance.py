"""Data provenance tracking for paper sources and quality."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


SOURCE_RELIABILITY: Dict[str, float] = {
    "pubmed": 0.95,
    "arxiv": 0.90,
    "openalex": 0.85,
    "semantic_scholar": 0.80,
    "huggingface": 0.75,
    "crossref": 0.70,
    "manual": 0.50,
    "unknown": 0.30,
}


def get_source_reliability(source: str) -> float:
    """Get reliability score for a source."""
    return SOURCE_RELIABILITY.get(source.lower(), SOURCE_RELIABILITY["unknown"])


def build_provenance(
    source: str,
    source_id: str = "",
    fetched_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a provenance payload for a paper."""
    return {
        "source": source.lower(),
        "source_id": source_id,
        "source_reliability": get_source_reliability(source),
        "validation_status": "pending",
        "validation_errors": [],
        "quality_score": None,
        "duplicate_of": None,
        "merged_into": None,
        "merged_sources": [],
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def mark_validated(provenance: Dict[str, Any], errors: List[str] = None) -> Dict[str, Any]:
    """Mark provenance as validated."""
    prov = dict(provenance)
    prov["validation_status"] = "valid" if not errors else "invalid"
    prov["validation_errors"] = errors or []
    return prov


def mark_duplicate(provenance: Dict[str, Any], original_id: str) -> Dict[str, Any]:
    """Mark provenance as duplicate of another paper."""
    prov = dict(provenance)
    prov["duplicate_of"] = original_id
    prov["validation_status"] = "duplicate"
    return prov


def mark_merged(provenance: Dict[str, Any], merged_into_id: str, merged_source: Dict[str, Any]) -> Dict[str, Any]:
    """Mark provenance as merged into another paper."""
    prov = dict(provenance)
    prov["merged_into"] = merged_into_id
    prov["validation_status"] = "merged"
    prov["merged_sources"] = prov.get("merged_sources", []) + [merged_source]
    return prov


def merge_provenance(
    primary: Dict[str, Any],
    secondary: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge two provenance records, keeping the best fields."""
    merged = dict(primary)
    if secondary.get("source_reliability", 0) > primary.get("source_reliability", 0):
        merged["source"] = secondary["source"]
        merged["source_reliability"] = secondary["source_reliability"]
    merged["merged_sources"] = primary.get("merged_sources", []) + [
        {
            "source": secondary.get("source", "unknown"),
            "source_id": secondary.get("source_id", ""),
            "reliability": secondary.get("source_reliability", 0),
            "merged_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    return merged
