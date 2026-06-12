import pytest
from datetime import datetime
from uuid import uuid4
from src.models import Paper, Finding, Contradiction, Bottleneck, Hypothesis
from src.config import settings


class TestModels:
    def test_paper_creation(self):
        paper = Paper(
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author A"],
            source="arxiv",
            source_id="1234.56789",
        )
        assert paper.title == "Test Paper"
        assert paper.source == "arxiv"
        assert paper.status.value == "pending"
        assert isinstance(paper.id, uuid4().__class__)

    def test_finding_creation(self):
        paper_id = uuid4()
        finding = Finding(
            paper_id=paper_id,
            finding_text="Test finding",
            confidence=0.95,
        )
        assert finding.paper_id == paper_id
        assert finding.confidence == 0.95

    def test_contradiction_creation(self):
        finding_a_id = uuid4()
        finding_b_id = uuid4()
        contradiction = Contradiction(
            finding_a_id=finding_a_id,
            finding_b_id=finding_b_id,
            contradiction_type="methodological",
            explanation="Different methods used",
            confidence=0.8,
        )
        assert contradiction.finding_a_id == finding_a_id
        assert contradiction.finding_b_id == finding_b_id

    def test_bottleneck_creation(self):
        bottleneck = Bottleneck(
            field="Cancer Research",
            description="Limited drug delivery",
            major_bottleneck="Tumor delivery systems",
            confidence=0.82,
        )
        assert bottleneck.field == "Cancer Research"
        assert bottleneck.major_bottleneck == "Tumor delivery systems"

    def test_hypothesis_creation(self):
        hypothesis = Hypothesis(
            hypothesis_text="CRISPR can modulate neural circuits",
            confidence=0.76,
        )
        assert hypothesis.confidence == 0.76
        assert len(hypothesis.suggested_experiments) == 0


class TestSettings:
    def test_settings_defaults(self):
        assert settings.APP_NAME == "GSM-OS"
        assert settings.QDRANT_COLLECTION == "scientific_memory"
        assert settings.EMBEDDING_MODEL == "all-MiniLM-L6-v2"

    def test_settings_from_env(self, monkeypatch):
        monkeypatch.setenv("FASTAPI_PORT", "9000")
        from src.config import get_settings
        test_settings = get_settings()
        assert test_settings.FASTAPI_PORT == 8000  # Default since already loaded


class TestPaperSource:
    def test_paper_source_enum_values(self):
        from src.models import PaperSource
        assert PaperSource.ARXIV.value == "arxiv"
        assert PaperSource.PUBMED.value == "pubmed"
        assert PaperSource.NATURE.value == "nature"


class TestPaperStatus:
    def test_paper_status_transitions(self):
        from src.models import PaperStatus
        assert PaperStatus.PENDING.value == "pending"
        assert PaperStatus.PROCESSING.value == "processing"
        assert PaperStatus.INDEXED.value == "indexed"
        assert PaperStatus.FAILED.value == "failed"
