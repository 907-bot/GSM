import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models import Paper


@pytest.fixture
def mock_memory():
    with patch('src.agents.research_agent.EpisodicMemory') as mock_ep, \
         patch('src.agents.research_agent.SemanticMemory') as mock_sem:
        mock_ep.return_value.store_paper = AsyncMock(return_value="embed-123")
        mock_ep.return_value.search_similar = AsyncMock(return_value=[])
        mock_sem.return_value.link_paper_to_concepts = AsyncMock(return_value=True)
        mock_sem.return_value.create_concept = AsyncMock(return_value="concept-123")
        yield


@pytest.mark.usefixtures("mock_memory")
class TestBaseResearchAgent:
    @pytest.mark.asyncio
    async def test_extract_concepts(self):
        from src.agents.research_agent import BaseResearchAgent
        agent = BaseResearchAgent(domain="test", keywords=["test", "keyword"])
        paper = Paper(
            title="Test Paper",
            abstract="Test abstract",
            source="arxiv",
            source_id="1234.56789",
            categories=["cat1", "cat2"],
        )
        concepts = await agent._extract_concepts(paper)
        assert "cat1" in concepts
        assert "cat2" in concepts
        assert "test" in concepts

    @pytest.mark.asyncio
    async def test_process_paper(self):
        from src.agents.research_agent import BaseResearchAgent
        agent = BaseResearchAgent(domain="test", keywords=[])
        with patch('src.agents.research_agent.embedding_service.embed_paper',
                   new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 384
            paper = await agent.process_paper({
                "title": "Test",
                "abstract": "Test abstract",
                "authors": ["Author A"],
                "source": "arxiv",
                "source_id": "1234.56789",
                "categories": ["cs.AI"],
            })
            assert paper is not None
            assert paper.title == "Test"


@pytest.mark.usefixtures("mock_memory")
class TestDomainAgents:
    def test_biology_agent_creation(self):
        from src.agents.research_agent import BiologyAgent
        agent = BiologyAgent()
        assert agent.domain == "biology"
        assert "CRISPR" in agent.keywords

    def test_ai_agent_creation(self):
        from src.agents.research_agent import AIAgent
        agent = AIAgent()
        assert agent.domain == "ai"
        assert "graph neural networks" in agent.keywords

    def test_materials_agent_creation(self):
        from src.agents.research_agent import MaterialsAgent
        agent = MaterialsAgent()
        assert agent.domain == "materials"
        assert "superconductors" in agent.keywords

    def test_medicine_agent_creation(self):
        from src.agents.research_agent import MedicineAgent
        agent = MedicineAgent()
        assert agent.domain == "medicine"
        assert "drug discovery" in agent.keywords

    def test_chemistry_agent_creation(self):
        from src.agents.research_agent import ChemistryAgent
        agent = ChemistryAgent()
        assert agent.domain == "chemistry"
        assert "catalysis" in agent.keywords

    def test_physics_agent_creation(self):
        from src.agents.research_agent import PhysicsAgent
        agent = PhysicsAgent()
        assert agent.domain == "physics"
        assert "quantum computing" in agent.keywords

    def test_get_all_agents(self):
        from src.agents.research_agent import get_all_agents
        agents = get_all_agents()
        assert len(agents) == 6
        domains = [a.domain for a in agents]
        assert "biology" in domains
        assert "ai" in domains
        assert "materials" in domains
        assert "medicine" in domains
        assert "chemistry" in domains
        assert "physics" in domains
