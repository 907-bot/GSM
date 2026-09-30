"""Paper validation, enrichment, and quality scoring."""

import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from ..memory.provenance import SOURCE_RELIABILITY

DOI_PATTERN = re.compile(r"^10\.\d{4,}/.+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
MIN_ABSTRACT_LENGTH = 10
MAX_TITLE_LENGTH = 500


def validate_paper(paper: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a paper dictionary. Returns (is_valid, list_of_errors)."""
    errors: List[str] = []

    title = paper.get("title", "").strip()
    if not title:
        errors.append("Missing required field: title")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Title too long: {len(title)} chars (max {MAX_TITLE_LENGTH})")

    abstract = paper.get("abstract", "").strip()
    if not abstract:
        errors.append("Missing required field: abstract")
    elif len(abstract) < MIN_ABSTRACT_LENGTH:
        errors.append(f"Abstract too short: {len(abstract)} chars (min {MIN_ABSTRACT_LENGTH})")

    source = paper.get("source", "").strip().lower()
    if not source:
        errors.append("Missing required field: source")

    doi = paper.get("doi")
    if doi and not DOI_PATTERN.match(str(doi).strip()):
        errors.append(f"Invalid DOI format: {doi}")

    published_at = paper.get("published_at")
    if published_at:
        if not DATE_PATTERN.match(str(published_at)):
            errors.append(f"Invalid date format: {published_at} (expected YYYY-MM-DD)")
        else:
            try:
                datetime.strptime(str(published_at)[:10], "%Y-%m-%d")
            except ValueError:
                errors.append(f"Invalid date: {published_at}")

    authors = paper.get("authors", [])
    if not isinstance(authors, list):
        errors.append("authors must be a list")

    categories = paper.get("categories", [])
    if not isinstance(categories, list):
        errors.append("categories must be a list")

    return len(errors) == 0, errors


def score_paper_quality(paper: Dict[str, Any]) -> float:
    """Compute a quality score (0-1) for a paper."""
    score = 0.0
    weights = {
        "has_abstract": 0.25,
        "has_doi": 0.10,
        "has_authors": 0.15,
        "has_categories": 0.10,
        "abstract_length": 0.15,
        "source_reliability": 0.25,
    }

    abstract = paper.get("abstract", "")
    if abstract and len(abstract) >= MIN_ABSTRACT_LENGTH:
        score += weights["has_abstract"]
        length_score = min(1.0, len(abstract) / 500)
        score += weights["abstract_length"] * length_score

    if paper.get("doi"):
        score += weights["has_doi"]

    authors = paper.get("authors", [])
    if isinstance(authors, list) and len(authors) > 0:
        score += weights["has_authors"]

    categories = paper.get("categories", [])
    if isinstance(categories, list) and len(categories) > 0:
        score += weights["has_categories"]

    source = paper.get("source", "unknown").lower()
    source_score = SOURCE_RELIABILITY.get(source, SOURCE_RELIABILITY["unknown"])
    score += weights["source_reliability"] * source_score

    provenance = paper.get("provenance", {})
    if provenance.get("quality_score") is not None:
        score = (score + float(provenance["quality_score"])) / 2

    return round(min(1.0, max(0.0, score)), 3)


def enrich_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-detect and fill missing paper fields."""
    enriched = dict(paper)

    if not enriched.get("source"):
        enriched["source"] = "unknown"

    if not enriched.get("source_id"):
        enriched["source_id"] = ""

    authors = enriched.get("authors", [])
    if not authors:
        enriched["authors"] = []

    categories = enriched.get("categories", [])
    if not categories:
        detected = _detect_categories(enriched.get("title", ""), enriched.get("abstract", ""))
        if detected:
            enriched["categories"] = detected

    return enriched


CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "cs.AI": ["artificial intelligence", "machine learning", "deep learning", "neural network", "transformer", "llm", "large language model", "reinforcement learning"],
    "cs.CV": ["computer vision", "image", "object detection", "segmentation", "visual", "video", "convolutional"],
    "cs.CL": ["natural language", "language model", "nlp", "text", "translation", "sentiment", "token"],
    "cs.LG": ["learning", "gradient", "classification", "regression", "dataset", "training", "generalization"],
    "cs.RO": ["robot", "control", "autonomous", "manipulation", "navigation", "grasp"],
    "cs.ET": ["neuromorphic", "spiking", "emerging", "device", "hardware"],
    "q-bio.BM": ["molecular", "protein", "binding", "docking", "molecule", "drug", "ligand", "biomolecular"],
    "q-bio.GN": ["genome", "gene", "genetic", "genomics", "dna", "rna", "crispr", "sequencing"],
    "cond-mat.supr-con": ["superconduct", "superconducting", "critical temperature", "hydride", "pairing"],
    "physics.app-ph": ["applied physics", "device", "sensor", "photonic", "optical"],
    "astro-ph.CO": ["cosmolog", "galaxy", "dark matter", "dark energy", "inflation", "cmb"],
    "eess.SP": ["signal", "estimation", "filter", "detection", "sampling", "adaptive"],
    "Medicine": ["clinical", "patient", "treatment", "diagnosis", "disease", "therapy", "medical", "oncology"],
    "Drug Discovery": ["drug", "discovery", "pharma", "compound", "screening", "lead optimization"],
    "Genetics": ["crispr", "gene", "genome", "cas9", "editing", "therapy", "genetic"],
}

CATEGORY_FALLBACK = "Other"


def _detect_categories(title: str, abstract: str) -> List[str]:
    """Detect categories from title and abstract using keyword matching."""
    text = (title + " " + abstract).lower()
    matched = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(category)
                break
    return matched[:5]
