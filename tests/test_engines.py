import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.engines.contradiction import ContradictionEngine
from src.engines.bottleneck import BottleneckEngine
from src.engines.hypothesis import HypothesisGenerator
from src.engines.graph_discovery import GraphDiscoveryEngine


@pytest.fixture
def mock_memory():
    with patch('src.engines.contradiction.EpisodicMemory') as mock_ep, \
         patch('src.engines.contradiction.SemanticMemory') as mock_sem, \
         patch('src.engines.bottleneck.EpisodicMemory') as mock_be, \
         patch('src.engines.bottleneck.SemanticMemory') as mock_bs, \
         patch('src.engines.hypothesis.EpisodicMemory') as mock_he, \
         patch('src.engines.hypothesis.SemanticMemory') as mock_hs, \
         patch('src.engines.graph_discovery.EpisodicMemory') as mock_ge, \
         patch('src.engines.graph_discovery.SemanticMemory') as mock_gs:
        mock_ep.return_value.search_similar = AsyncMock(return_value=[])
        mock_sem.return_value.get_statistics = AsyncMock(return_value={"concepts": 0, "papers": 0, "relationships": 0})
        mock_sem.return_value.find_hidden_relationships = AsyncMock(return_value=[])
        mock_be.return_value.search_similar = AsyncMock(return_value=[])
        mock_be.return_value.get_recent_papers = AsyncMock(return_value=[])
        mock_bs.return_value.get_statistics = AsyncMock(return_value={"concepts": 0, "papers": 0, "relationships": 0})
        mock_he.return_value.search_similar = AsyncMock(return_value=[])
        mock_hs.return_value.get_statistics = AsyncMock(return_value={"concepts": 0, "papers": 0, "relationships": 0})
        mock_hs.return_value.find_hidden_relationships = AsyncMock(return_value=[])
        mock_ge.return_value.get_recent_papers = AsyncMock(return_value=[])
        mock_ge.return_value.search_similar = AsyncMock(return_value=[])
        mock_gs.return_value.get_statistics = AsyncMock(return_value={"concepts": 0, "papers": 0, "relationships": 0})
        mock_gs.return_value.get_concept_neighbors = AsyncMock(return_value={"concept": "test", "neighbors": []})
        mock_gs.return_value.find_hidden_relationships = AsyncMock(return_value=[])
        yield


class TestContradictionEngine:
    @pytest.mark.asyncio
    async def test_detect_contradictions_empty(self, mock_memory):
        engine = ContradictionEngine()
        results = await engine.detect_contradictions([])
        assert results == []

    def test_contradiction_indicators_present(self):
        engine = ContradictionEngine()
        assert hasattr(engine, 'episodic')
        assert hasattr(engine, 'semantic')

    @pytest.mark.asyncio
    async def test_get_contradiction_summary(self, mock_memory):
        engine = ContradictionEngine()
        summary = await engine.get_contradiction_summary()
        assert "total_contradictions" in summary
        assert "by_type" in summary


class TestBottleneckEngine:
    @pytest.mark.asyncio
    async def test_detect_bottlenecks_empty_field(self, mock_memory):
        engine = BottleneckEngine()
        engine.episodic.search_similar = AsyncMock(return_value=[])
        results = await engine.detect_bottlenecks("")
        assert isinstance(results, list)

    def test_suggest_approaches(self):
        engine = BottleneckEngine()
        approaches = engine._suggest_approaches("challenge")
        assert len(approaches) > 0
        assert "Review existing solutions" in approaches

    def test_deduplicate_patterns(self):
        engine = BottleneckEngine()
        patterns = [
            {"major_bottleneck": "Test bottleneck A", "confidence": 0.8},
            {"major_bottleneck": "Test bottleneck A", "confidence": 0.9},
            {"major_bottleneck": "Test bottleneck B", "confidence": 0.7},
        ]
        unique = engine._deduplicate_patterns(patterns)
        assert len(unique) == 2
        # First occurrence of each key is kept, then sorted by confidence
        assert unique[0]["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_get_bottleneck_summary(self, mock_memory):
        engine = BottleneckEngine()
        engine.episodic.search_similar = AsyncMock(return_value=[])
        summary = await engine.get_bottleneck_summary("Test Field")
        assert "field" in summary
        assert "total_bottlenecks" in summary


class TestHypothesisGenerator:
    @pytest.mark.asyncio
    async def test_generate_hypotheses(self, mock_memory):
        engine = HypothesisGenerator()
        engine.episodic.search_similar = AsyncMock(return_value=[])
        hypotheses = await engine.generate_hypotheses(num_hypotheses=3)
        assert isinstance(hypotheses, list)

    @pytest.mark.asyncio
    async def test_evaluate_hypothesis(self, mock_memory):
        from src.models import Hypothesis
        engine = HypothesisGenerator()
        engine.episodic.search_similar = AsyncMock(return_value=[])
        hypothesis = Hypothesis(hypothesis_text="Test hypothesis", confidence=0.5)
        evaluation = await engine.evaluate_hypothesis(hypothesis)
        assert "confidence_adjustment" in evaluation
        assert "recommendations" in evaluation

    @pytest.mark.asyncio
    async def test_create_experiment_recommendation(self, mock_memory):
        from src.models import Hypothesis
        engine = HypothesisGenerator()
        hypothesis = Hypothesis(hypothesis_text="Test hypothesis", confidence=0.5)
        rec = await engine.create_experiment_recommendation(hypothesis)
        assert rec.title is not None
        assert len(rec.methods) > 0


class TestGraphDiscoveryEngine:
    @pytest.mark.asyncio
    async def test_analyze_graph_health(self, mock_memory):
        engine = GraphDiscoveryEngine()
        health = await engine.analyze_graph_health()
        assert "statistics" in health
        assert "density" in health
        assert "connectivity" in health
        assert "health_score" in health

    def test_calculate_density(self):
        engine = GraphDiscoveryEngine()
        stats = {"concepts": 10, "papers": 5, "relationships": 20}
        density = engine._calculate_density(stats)
        assert 0 <= density <= 1

    def test_calculate_density_zero_nodes(self):
        engine = GraphDiscoveryEngine()
        stats = {"concepts": 0, "papers": 0, "relationships": 0}
        density = engine._calculate_density(stats)
        assert density == 0.0

    @pytest.mark.asyncio
    async def test_visualize_subgraph(self, mock_memory):
        engine = GraphDiscoveryEngine()
        result = await engine.visualize_subgraph("CRISPR", depth=2)
        assert "nodes" in result
        assert "edges" in result
        assert "center" in result

    @pytest.mark.asyncio
    async def test_detect_emerging_clusters(self, mock_memory):
        engine = GraphDiscoveryEngine()
        engine.episodic.get_recent_papers = AsyncMock(return_value=[])
        clusters = await engine.detect_emerging_clusters()
        assert isinstance(clusters, list)

    @pytest.mark.asyncio
    async def test_find_missing_links(self, mock_memory):
        engine = GraphDiscoveryEngine()
        links = await engine.find_missing_links()
        assert isinstance(links, list)
