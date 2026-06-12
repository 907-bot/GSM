from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class PaperSource(str, Enum):
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    OPENALEX = "openalex"
    NATURE = "nature"
    SCIENCE = "science"
    CELL = "cell"
    IEEE = "ieee"
    ACM = "acm"


class PaperStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Paper(BaseModel):
    """Scientific paper model."""
    id: UUID = Field(default_factory=uuid4)
    title: str
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    doi: Optional[str] = None
    source: PaperSource
    source_id: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    indexed_at: datetime = Field(default_factory=datetime.now)
    status: PaperStatus = PaperStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    citations_count: int = 0
    embedding_id: Optional[str] = None


class Finding(BaseModel):
    """Scientific finding extracted from papers."""
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    finding_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class Contradiction(BaseModel):
    """Contradiction between findings."""
    id: UUID = Field(default_factory=uuid4)
    finding_a_id: UUID
    finding_b_id: UUID
    contradiction_type: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    resolution_suggestions: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.now)


class Bottleneck(BaseModel):
    """Scientific bottleneck."""
    id: UUID = Field(default_factory=uuid4)
    field: str
    description: str
    major_bottleneck: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_papers: List[UUID] = Field(default_factory=list)
    suggested_approaches: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.now)


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting a hypothesis."""
    paper_id: str
    title: str
    abstract: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    published_at: Optional[str] = None
    relevance_score: float = 0.5
    relationship: Optional[str] = None  # supporting / contradicting


class Hypothesis(BaseModel):
    """Generated hypothesis with full evidence trail."""
    id: UUID = Field(default_factory=uuid4)
    hypothesis_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: List[UUID] = Field(default_factory=list)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    suggested_experiments: List[str] = Field(default_factory=list)
    related_concepts: List[str] = Field(default_factory=list)
    source_category: Optional[str] = None  # findings / contradictions / patterns
    created_at: datetime = Field(default_factory=datetime.now)
    evaluated: bool = False
    evaluation_summary: Optional[str] = None


class GraphRelationship(BaseModel):
    """Relationship in the scientific graph."""
    id: UUID = Field(default_factory=uuid4)
    source_concept: str
    target_concept: str
    relationship_type: str
    weight: float = Field(ge=0.0, le=1.0)
    evidence_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class ResearchAlert(BaseModel):
    """Research alert for monitoring."""
    id: UUID = Field(default_factory=uuid4)
    domain: str
    keywords: List[str]
    papers_found: int = 0
    new_findings: List[Finding] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ExperimentRecommendation(BaseModel):
    """Recommended experiment."""
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    hypothesis_id: UUID
    materials: List[str] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    controls: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    estimated_duration: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
